import logging
import asyncio
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Union
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from pydantic import BaseModel, Field
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
from .rag import initialize_pipeline


def get_real_client_ip(request: Request) -> str:
    """Extract the real visitor IP from the X-Forwarded-For header set by Nginx,
    falling back to the direct connection address if the header is absent
    (e.g. in local development without a reverse proxy)."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        resolved_ip = forwarded_for.split(",")[0].strip()
    else:
        resolved_ip = request.client.host if request.client else "unknown"
    logger.warning(f"[RATE LIMIT DEBUG] Resolved client IP: {resolved_ip}")
    return resolved_ip


limiter = Limiter(key_func=get_real_client_ip)

logger = logging.getLogger(__name__)
QDRANT_COLLECTION_NAME = "redlib"
PROMPT_EXCERPT_CHARS = 500
TECHNIQUE_CATEGORIES = [
    ("Role-Based Task Framing", "psychology_alt"),
    ("Fictional / Hypothetical Framing", "movie"),
    ("Authority or Legitimacy Spoofing", "admin_panel_settings"),
    ("Obfuscation / Encoding", "code"),
    ("Simulation or Sandbox Framing", "science"),
    ("Dual-Response or Comparative Framing", "call_split"),
    ("Legitimate Context or Research Framing", "gavel"),
    ("Contextual Reframing or Euphemism", "edit_note"),
]
CATEGORY_CACHE_TTL_SECONDS = 300
CATEGORY_CACHE_LOCK = threading.Lock()
CATEGORY_CACHE: dict[str, object] = {
    "items": None,
    "expires_at": 0.0,
}


# Pydantic models
class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
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


class BrowseResultCard(BaseModel):
    id: str
    prompt_excerpt: str
    technique: str
    source: str


class BrowseResponse(BaseModel):
    results: List[BrowseResultCard]
    next_cursor: Optional[str]
    total: int
    category: str


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


def build_prompt_excerpt(text: str) -> str:
    """Keep prompt excerpts scan-friendly without splitting mid-word."""
    excerpt = text[:PROMPT_EXCERPT_CHARS]
    if len(text) > PROMPT_EXCERPT_CHARS:
        last_space = excerpt.rfind(" ")
        if last_space > 0:
            excerpt = excerpt[:last_space]
    return excerpt


REFUSAL_PATTERNS = [
    "i cannot provide",
    "i cannot analyze",
    "i can't provide",
    "i can't analyze",
    "i will not provide",
    "i'm not able to",
    "i am not able to",
    "i'm unable to",
    "i am unable to",
    "does not contain jailbreak prompts suitable",
]


def is_refusal(answer: str) -> bool:
    """Detect if the synthesizer output is a refusal rather than analysis."""
    lowered = answer.lower()
    return any(pattern in lowered for pattern in REFUSAL_PATTERNS)


def build_fallback_summary(technique_counts: Dict[str, int]) -> str:
    """Deterministic fallback summary built from real retrieved metadata,
    used when the LLM synthesis returns a refusal instead of analysis."""
    if not technique_counts:
        return "No dominant technique pattern was identified in the retrieved results."

    sorted_techniques = sorted(technique_counts.items(), key=lambda item: item[1], reverse=True)
    dominant_technique, dominant_count = sorted_techniques[0]
    total = sum(technique_counts.values())

    if len(sorted_techniques) == 1:
        return (
            f"The retrieved prompts are classified under {dominant_technique}, "
            f"appearing in {dominant_count} of {total} results."
        )

    other_names = ", ".join(name for name, _ in sorted_techniques[1:])
    return (
        f"{dominant_technique} is the dominant pattern in this result set, "
        f"appearing in {dominant_count} of {total} results, with additional "
        f"overlap into {other_names}."
    )


def validate_category_name(category: str) -> None:
    """Reject categories that are not in the approved taxonomy."""
    approved_categories = {name for name, _ in TECHNIQUE_CATEGORIES}
    if category not in approved_categories:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid category. Category must match one of the approved "
                "taxonomy technique names exactly."
            ),
        )


def parse_scroll_cursor(cursor: Optional[str]) -> Optional[Union[int, str]]:
    """Convert the frontend cursor token back into a Qdrant scroll offset."""
    if cursor is None or cursor == "":
        return None
    if cursor.isdigit():
        return int(cursor)
    return cursor


def get_category_total(category: str, client: QdrantClient) -> int:
    """Return the live count for one approved category using cached counts when available."""
    for item in get_cached_category_items(client):
        if item.name == category:
            return item.count
    return 0


def get_prompt_by_id(prompt_id: str, client: QdrantClient) -> PromptResponse:
    """Fetch a single prompt by metadata prompt_id directly from Qdrant."""
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


def get_category_items(client: QdrantClient) -> list[CategoryItem]:
    """Fetch live corpus counts for each technique category from Qdrant."""
    ensure_keyword_payload_index(client, "technique")

    categories: list[CategoryItem] = []
    for technique_name, icon in TECHNIQUE_CATEGORIES:
        count_result = client.count(
            collection_name=QDRANT_COLLECTION_NAME,
            count_filter=QdrantFilter(
                must=[
                    FieldCondition(
                        key="technique",
                        match=MatchValue(value=technique_name),
                    )
                ]
            ),
            exact=True,
        )
        categories.append(
            CategoryItem(
                name=technique_name,
                count=count_result.count,
                icon=icon,
            )
        )

    return categories


def browse_category(
    category: str,
    cursor: Optional[str],
    limit: int,
    client: QdrantClient,
) -> BrowseResponse:
    """Scroll Qdrant directly for deterministic category browsing."""
    ensure_keyword_payload_index(client, "technique")

    total = get_category_total(category, client)
    if total == 0:
        raise LookupError(category)

    records, next_page_offset = client.scroll(
        collection_name=QDRANT_COLLECTION_NAME,
        scroll_filter=QdrantFilter(
            must=[
                FieldCondition(
                    key="technique",
                    match=MatchValue(value=category),
                )
            ]
        ),
        offset=parse_scroll_cursor(cursor),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    results: list[BrowseResultCard] = []
    for record in records:
        payload = record.payload or {}
        node = metadata_dict_to_node(payload)
        text = node.get_content(metadata_mode=MetadataMode.NONE)
        results.append(
            BrowseResultCard(
                id=payload.get("prompt_id", ""),
                prompt_excerpt=build_prompt_excerpt(text),
                technique=payload.get("technique", "Unknown"),
                source=payload.get("source", ""),
            )
        )

    return BrowseResponse(
        results=results,
        next_cursor=str(next_page_offset) if next_page_offset is not None else None,
        total=total,
        category=category,
    )


def get_cached_category_items(client: QdrantClient) -> list[CategoryItem]:
    """Return cached category counts when fresh, otherwise refresh them."""
    now = time.monotonic()

    with CATEGORY_CACHE_LOCK:
        cached_items = CATEGORY_CACHE["items"]
        expires_at = CATEGORY_CACHE["expires_at"]
        if cached_items is not None and now < expires_at:
            return list(cached_items)

    categories = get_category_items(client)

    with CATEGORY_CACHE_LOCK:
        CATEGORY_CACHE["items"] = list(categories)
        CATEGORY_CACHE["expires_at"] = time.monotonic() + CATEGORY_CACHE_TTL_SECONDS

    return categories


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        app.state.qdrant_client = get_qdrant_client()
        query_engine, index_obj, reranker, synthesizer = initialize_pipeline()
        app.state.query_engine = query_engine
        app.state.index_obj = index_obj
        app.state.reranker = reranker
        app.state.synthesizer = synthesizer
        logger.info("FastAPI app initialized with query engine")
    except Exception as e:
        logger.error("Failed to initialize pipeline on startup", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("FastAPI app shutting down")


# Create FastAPI app
app = FastAPI(title="RedLib", version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://redlib.bynipun.com"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/query")
@limiter.limit("10/minute")
async def query(request: Request, query_request: QueryRequest) -> QueryResponse:
    """
    Main RAG query endpoint.

    Routes all queries through the corpus-grounded retrieval pipeline.
    Applies category filter if provided.
    """
    if query_request.category_filter:
        validate_category_name(query_request.category_filter)

    try:
        from .retriever import get_filtered_retriever
        from llama_index.core.query_engine import RetrieverQueryEngine

        if query_request.category_filter:
            filtered_retriever = get_filtered_retriever(
                app.state.index_obj, query_request.category_filter
            )
            engine = RetrieverQueryEngine.from_args(
                retriever=filtered_retriever,
                node_postprocessors=[app.state.reranker],
                response_synthesizer=app.state.synthesizer,
            )
        else:
            engine = app.state.query_engine

        # Run query in thread executor (query_engine.query is synchronous)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: engine.query(query_request.query),
        )

        # Build results array and technique breakdown
        results: List[ResultCard] = []
        technique_counts: Dict[str, int] = {}

        for node in response.source_nodes:
            metadata = node.metadata
            text = node.get_content(metadata_mode=MetadataMode.NONE)

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
                prompt_excerpt=build_prompt_excerpt(text),
                technique=technique,
                source=metadata.get("source", ""),
                confidence=confidence,
                confidence_score=score,
            )
            results.append(result_card)

        answer_text = response.response or ""
        if is_refusal(answer_text):
            logger.warning(f"Synthesizer returned a refusal, using fallback summary. Original: {answer_text[:200]}")
            answer_text = build_fallback_summary(technique_counts)

        return QueryResponse(
            answer=answer_text,
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
    Returns all 8 technique categories with live corpus counts.
    """
    try:
        loop = asyncio.get_event_loop()
        categories = await loop.run_in_executor(
            None,
            lambda: get_cached_category_items(app.state.qdrant_client),
        )
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


@app.get("/api/browse")
async def get_browse_results(
    category: str,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> BrowseResponse:
    """
    Browse one approved technique category using direct Qdrant scroll pagination.
    """
    validate_category_name(category)
    if limit < 1 or limit > 50:
        raise HTTPException(
            status_code=400,
            detail="Invalid limit. Limit must be between 1 and 50.",
        )

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: browse_category(
                category=category,
                cursor=cursor,
                limit=limit,
                client=app.state.qdrant_client,
            ),
        )
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Approved category exists but no prompts were found in Qdrant.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to browse category {category}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to browse category prompts",
        )


@app.get("/api/prompts/{prompt_id}")
@limiter.limit("30/minute")
async def get_prompt(request: Request, prompt_id: str) -> PromptResponse:
    """Fetch a single full prompt on demand without running the RAG pipeline."""
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: get_prompt_by_id(prompt_id, app.state.qdrant_client),
        )
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
            lambda: app.state.qdrant_client.count(
                collection_name=QDRANT_COLLECTION_NAME,
                exact=True,
            ).count,
        )

        return StatsResponse(
            total_prompts=total_prompts,
            total_sources=7,
            last_sync="2026-07-10",
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
