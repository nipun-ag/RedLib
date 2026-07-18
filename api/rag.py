import logging
from typing import Any
from llama_index.core.query_engine import RetrieverQueryEngine
from .embedder import get_embed_model
from .retriever import get_retriever, get_reranker
from .synthesizer import get_synthesizer
from .router import get_query_engine

logger = logging.getLogger(__name__)


def initialize_pipeline() -> tuple[RetrieverQueryEngine, Any, Any, Any]:
    """
    Assemble the full LlamaIndex query pipeline by connecting all components.
    Called once at server startup by app.py. Never run directly.

    Returns:
        Tuple of (query_engine, index_obj, reranker, synthesizer). The
        latter three are returned alongside the assembled query engine so
        app.py can build isolated per-request filtered retrievers without
        mutating the shared query_engine's retriever state.
    """
    try:
        embed_model = get_embed_model()
        logger.info("Step 1/5: Embedding model initialized")

        retriever, index_obj = get_retriever(embed_model)
        logger.info("Step 2/5: Retriever initialized")

        reranker = get_reranker()
        logger.info("Step 3/5: Reranker initialized")

        synthesizer = get_synthesizer()
        logger.info("Step 4/5: Synthesizer initialized")

        query_engine = get_query_engine(retriever, reranker, synthesizer)
        logger.info("Step 5/5: Corpus-grounded query engine assembled. Pipeline ready.")

        return query_engine, index_obj, reranker, synthesizer

    except Exception as e:
        logger.error(f"Pipeline initialization failed: {str(e)}", exc_info=True)
        raise
