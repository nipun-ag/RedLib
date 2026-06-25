import os
import logging
from llama_index.core.query_engine import RouterQueryEngine
from embedder import get_embed_model
from retriever import get_retriever, get_reranker
from synthesizer import get_synthesizer, get_llm
from router import get_query_engine_tools, get_router

logger = logging.getLogger(__name__)


def initialize_pipeline() -> RouterQueryEngine:
    """
    Assemble the full LlamaIndex query pipeline by connecting all components.
    Called once at server startup by app.py. Never run directly.

    Steps:
    1. Initialize embedding model
    2. Initialize retriever (connects to Qdrant internally)
    3. Initialize reranker
    4. Initialize synthesizer
    5. Initialize LLM for router
    6. Assemble router

    Returns:
        RouterQueryEngine: The fully configured query pipeline

    Raises:
        ValueError: If required environment variables are missing
        Exception: Re-raised after logging full traceback on any other error
    """
    try:
        # Step 1: Initialize embedding model
        embed_model = get_embed_model()
        logger.info("Step 1/6: Embedding model initialized")

        # Step 2: Initialize retriever (connects to Qdrant internally)
        retriever = get_retriever(embed_model)
        logger.info("Step 2/6: Retriever initialized")

        # Step 3: Initialize reranker
        reranker = get_reranker()
        logger.info("Step 3/6: Reranker initialized")

        # Step 4: Initialize synthesizer
        synthesizer = get_synthesizer()
        logger.info("Step 4/6: Synthesizer initialized")

        # Step 5: Initialize LLM for router
        llm = get_llm()
        logger.info("Step 5/6: LLM initialized")

        # Step 6: Assemble router
        tools = get_query_engine_tools(retriever, reranker, synthesizer)
        router = get_router(tools, llm)
        logger.info("Step 6/6: Router assembled. Pipeline ready.")

        return router

    except Exception as e:
        logger.error(f"Pipeline initialization failed: {str(e)}", exc_info=True)
        raise
