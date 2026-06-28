import logging
import asyncio
import os
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


def get_prompt_by_id(prompt_id: str) -> PromptResponse:
    """Fetch a single prompt by metadata prompt_id directly from Qdrant."""
    client = get_qdrant_client()
    collection_info = client.get_collection(QDRANT_COLLECTION_NAME)
    payload_schema = collection_info.payload_schema or {}

    if "prompt_id" not in payload_schema:
        logger.info("Creating missing Qdrant keyword payload index for prompt_id")
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION_NAME,
            field_name="prompt_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )

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
        if request.category_filter:
            filters = MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="technique",
                        value=request.category_filter,
                        operator=FilterOperator.EQ,
                    )
                ]
            )

        # Run query in thread executor (query_engine.query is synchronous)
        loop = asyncio.get_event_loop()
        if filters:
            response = await loop.run_in_executor(
                None,
                lambda: app.state.query_engine.query(
                    request.query, filters=filters
                ),
            )
        else:
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


@app.get("/api/categories")
async def get_categories() -> CategoriesResponse:
    """
    Returns all 10 technique categories with counts.

    Phase 1: Counts remain hardcoded as 0.
    """
    categories = [
        {"name": "Persona Hijacking", "count": 0, "icon": "psychology_alt"},
        {"name": "Fictional Framing", "count": 0, "icon": "movie"},
        {
            "name": "Authority Impersonation",
            "count": 0,
            "icon": "admin_panel_settings",
        },
        {"name": "Token Manipulation", "count": 0, "icon": "code"},
        {"name": "Gradual Escalation", "count": 0, "icon": "trending_up"},
        {
            "name": "Hypothetical Distancing",
            "count": 0,
            "icon": "science",
        },
        {"name": "Instruction Injection", "count": 0, "icon": "edit_note"},
        {
            "name": "Social Engineering",
            "count": 0,
            "icon": "sentiment_very_dissatisfied",
        },
        {
            "name": "Multi-language Switching",
            "count": 0,
            "icon": "translate",
        },
        {"name": "Payload Splitting", "count": 0, "icon": "call_split"},
    ]
    return CategoriesResponse(categories=categories)


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
