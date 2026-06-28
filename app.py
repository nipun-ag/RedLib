import logging
import asyncio
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from llama_index.core.schema import MetadataMode
from llama_index.core.vector_stores.utils import metadata_dict_to_node
from llama_index.core.vector_stores import (
    MetadataFilters,
    MetadataFilter,
    FilterOperator,
)
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Filter as QdrantFilter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)
from rag import initialize_pipeline

logger = logging.getLogger(__name__)
QDRANT_COLLECTION_NAME = "redlib"
TECHNIQUE_CATEGORIES = [
    ("Persona Hijacking", "psychology_alt"),
    ("Fictional Framing", "movie"),
    ("Authority Impersonation", "admin_panel_settings"),
    ("Token Manipulation", "code"),
    ("Gradual Escalation", "trending_up"),
    ("Hypothetical Distancing", "science"),
    ("Instruction Injection", "edit_note"),
    ("Social Engineering", "sentiment_very_dissatisfied"),
    ("Multi-language Switching", "translate"),
    ("Payload Splitting", "call_split"),
]
CATEGORY_CACHE_TTL_SECONDS = 300
CATEGORY_CACHE_LOCK = threading.Lock()
CATEGORY_CACHE: dict[str, object] = {
    "items": None,
    "expires_at": 0.0,
}


# Pydantic models
class QueryRequest(BaseModel):
    query: str
    category_filter: Optional[str] = None


class ResultCard(BaseModel):
    id: str
    prompt_excerpt: str
    technique: str
    source: str
    confidence: str
    confidence_score: float


class QueryResponse(BaseModel):
    answer: str
    results: List[ResultCard]
    technique_breakdown: Dict[str, int]
    result_count: int
    query_type: str


class CategoryItem(BaseModel):
    name: str
    count: int
    icon: str


class CategoriesResponse(BaseModel):
    categories: List[CategoryItem]


class StatsResponse(BaseModel):
    total_prompts: int
    total_sources: int
    last_sync: str


class PromptResponse(BaseModel):
    id: str
    full_prompt: str
    technique: str
    source: str


def get_qdrant_client() -> QdrantClient:
    """Configure and return a Qdrant client for lightweight app queries."""
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")

    if not qdrant_url:
        error_msg = "QDRANT_URL environment variable not set"
        logger.error(error_msg)
        raise ValueError(error_msg)

    if not qdrant_api_key:
        error_msg = "QDRANT_API_KEY environment variable not set"
        logger.error(error_msg)
        raise ValueError(error_msg)

    return QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
        timeout=120,
    )


def ensure_keyword_payload_index(client: QdrantClient, field_name: str) -> None:
    """Ensure a keyword payload index exists for a field used in Qdrant filters."""
    collection_info = client.get_collection(QDRANT_COLLECTION_NAME)
    payload_schema = collection_info.payload_schema or {}

    if field_name in payload_schema:
        return

    logger.info(f"Creating missing Qdrant keyword payload index for {field_name}")
    client.create_payload_index(
        collection_name=QDRANT_COLLECTION_NAME,
        field_name=field_name,
        field_schema=PayloadSchemaType.KEYWORD,
    )


def get_prompt_by_id(prompt_id: str) -> PromptResponse:
    """Fetch a single prompt by metadata prompt_id directly from Qdrant."""
    client = get_qdrant_client()
    ensure_keyword_payload_index(client, "prompt_id")

    records, _ = client.scroll(
        collection_name=QDRANT_COLLECTION_NAME,
        scroll_filter=QdrantFilter(
            must=[
                FieldCondition(
                    key="prompt_id",
                    match=MatchValue(value=prompt_id),
                )
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )

    if not records:
        raise KeyError(prompt_id)

    payload = records[0].payload or {}
    node = metadata_dict_to_node(payload)

    return PromptResponse(
        id=payload.get("prompt_id", prompt_id),
        full_prompt=node.get_content(metadata_mode=MetadataMode.NONE),
        technique=payload.get("technique", "Unknown"),
        source=payload.get("source", ""),
    )


def get_category_items() -> list[CategoryItem]:
    """Fetch live corpus counts for each technique category from Qdrant."""
    client = get_qdrant_client()
    technique_counts = {
        technique_name: 0 for technique_name, _ in TECHNIQUE_CATEGORIES
    }

    next_page_offset = None
    while True:
        records, next_page_offset = client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=1000,
            offset=next_page_offset,
            with_payload=True,
            with_vectors=False,
        )

        for record in records:
            payload = record.payload or {}
            technique_name = payload.get("technique")
            if technique_name in technique_counts:
                technique_counts[technique_name] += 1

        if next_page_offset is None:
            break

    categories: list[CategoryItem] = []
    for technique_name, icon in TECHNIQUE_CATEGORIES:
        categories.append(
            CategoryItem(
                name=technique_name,
                count=technique_counts[technique_name],
                icon=icon,
            )
        )

    return categories


def get_cached_category_items() -> list[CategoryItem]:
    """Return cached category counts when fresh, otherwise refresh them."""
    now = time.monotonic()

    with CATEGORY_CACHE_LOCK:
        cached_items = CATEGORY_CACHE["items"]
        expires_at = CATEGORY_CACHE["expires_at"]
        if cached_items is not None and now < expires_at:
            return list(cached_items)

    categories = get_category_items()

    with CATEGORY_CACHE_LOCK:
        CATEGORY_CACHE["items"] = list(categories)
        CATEGORY_CACHE["expires_at"] = time.monotonic() + CATEGORY_CACHE_TTL_SECONDS

    return categories


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        query_engine = initialize_pipeline()
        app.state.query_engine = query_engine
        logger.info("FastAPI app initialized with query engine")
    except Exception as e:
        logger.error("Failed to initialize pipeline on startup", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("FastAPI app shutting down")


# Create FastAPI app
app = FastAPI(title="RedLib", version="0.1.0", lifespan=lifespan)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/query")
async def query(request: QueryRequest) -> QueryResponse:
    """
    Main RAG query endpoint.

    Routes all queries through the corpus-grounded retrieval pipeline.
    Applies category filter if provided.
    """
    try:
        # Build metadata filters if category_filter provided
        filters = None
        retriever_filters = []
        if request.category_filter:
            client = get_qdrant_client()
            ensure_keyword_payload_index(client, "technique")
            filters = MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="technique",
                        value=request.category_filter,
                        operator=FilterOperator.EQ,
                    )
                ]
            )

            fusion_retriever = app.state.query_engine.retriever
            retriever_filters = [
                (retriever, getattr(retriever, "_filters", None))
                for retriever in getattr(fusion_retriever, "_retrievers", [])
            ]
            for retriever, _ in retriever_filters:
                retriever._filters = filters

        # Run query in thread executor (query_engine.query is synchronous)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: app.state.query_engine.query(request.query),
        )

        # Build results array and technique breakdown
        results: List[ResultCard] = []
        technique_counts: Dict[str, int] = {}

        for node in response.source_nodes:
            metadata = node.metadata
            text = node.get_content(metadata_mode=MetadataMode.NONE)

            # Truncate to 300 chars without splitting words
            excerpt = text[:300]
            if len(text) > 300:
                last_space = excerpt.rfind(" ")
                if last_space > 0:
                    excerpt = excerpt[:last_space]

            technique = metadata.get("technique", "Unknown")
            technique_counts[technique] = technique_counts.get(technique, 0) + 1

            # Map relevance score to confidence label
            score = node.score or 0.0
            if score >= 0.7:
                confidence = "HIGH"
            elif score >= 0.4:
                confidence = "MED"
            else:
                confidence = "LOW"

            result_card = ResultCard(
                id=metadata.get("prompt_id", ""),
                prompt_excerpt=excerpt,
                technique=technique,
                source=metadata.get("source", ""),
                confidence=confidence,
                confidence_score=score,
            )
            results.append(result_card)

        return QueryResponse(
            answer=response.response or "",
            results=results,
            technique_breakdown=technique_counts,
            result_count=len(results),
            query_type="semantic",
        )

    except Exception as e:
        logger.error("Query pipeline error", exc_info=True)
        raise HTTPException(status_code=500, detail="Query pipeline error")
    finally:
        for retriever, original_filters in retriever_filters:
            retriever._filters = original_filters


@app.get("/api/categories")
async def get_categories() -> CategoriesResponse:
    """
    Returns all 10 technique categories with live corpus counts.
    """
    try:
        loop = asyncio.get_event_loop()
        categories = await loop.run_in_executor(None, get_cached_category_items)
        return CategoriesResponse(categories=categories)
    except Exception as e:
        logger.error(
            f"Failed to load category counts from Qdrant: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to load category counts",
        )


@app.get("/api/prompts/{prompt_id}")
async def get_prompt(prompt_id: str) -> PromptResponse:
    """Fetch a single full prompt on demand without running the RAG pipeline."""
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: get_prompt_by_id(prompt_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Prompt not found")
    except Exception as e:
        logger.error(
            f"Failed to load prompt {prompt_id} from Qdrant: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to load prompt from Qdrant",
        )


@app.get("/api/stats")
async def get_stats() -> StatsResponse:
    """
    Returns corpus statistics for the stats bar.
    """
    try:
        loop = asyncio.get_event_loop()
        total_prompts = await loop.run_in_executor(
            None,
            lambda: get_qdrant_client().count(
                collection_name=QDRANT_COLLECTION_NAME,
                exact=True,
            ).count,
        )

        return StatsResponse(
            total_prompts=total_prompts,
            total_sources=4,
            last_sync="2026-06-28",
        )
    except Exception as e:
        logger.error(
            f"Failed to load stats from Qdrant: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to load live corpus stats from Qdrant",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
