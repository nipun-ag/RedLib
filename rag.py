import logging
from llama_index.core.query_engine import RetrieverQueryEngine
from embedder import get_embed_model
from retriever import get_retriever, get_reranker
from synthesizer import get_synthesizer
from router import get_query_engine

logger = logging.getLogger(__name__)


def initialize_pipeline() -> RetrieverQueryEngine:
    """
    Assemble the full LlamaIndex query pipeline by connecting all components.
    Called once at server startup by app.py. Never run directly.

    Steps:
    1. Initialize embedding model
    2. Initialize retriever (connects to Qdrant internally)
    3. Initialize reranker
    4. Initialize synthesizer
    5. Assemble a single corpus-grounded query engine

    Returns:
        RetrieverQueryEngine: The fully configured query pipeline

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
        logger.info("Step 4/5: Synthesizer initialized")

        # Step 5: Assemble a single corpus-grounded query engine
        query_engine = get_query_engine(retriever, reranker, synthesizer)
        logger.info("Step 5/5: Corpus-grounded query engine assembled. Pipeline ready.")

        return query_engine

    except Exception as e:
        logger.error(f"Pipeline initialization failed: {str(e)}", exc_info=True)
        raise
