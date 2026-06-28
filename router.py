import logging
from llama_index.core.query_engine import RetrieverQueryEngine

logger = logging.getLogger(__name__)


def get_query_engine(retriever, reranker, synthesizer) -> RetrieverQueryEngine:
    """Create a single corpus-grounded query engine for all user queries.

    Args:
        retriever: Configured QueryFusionRetriever
        reranker: Configured CohereRerank postprocessor
        synthesizer: Configured ResponseSynthesizer

    Returns:
        RetrieverQueryEngine configured for Qdrant-backed retrieval
    """
    try:
        query_engine = RetrieverQueryEngine.from_args(
            retriever=retriever,
            node_postprocessors=[reranker],
            response_synthesizer=synthesizer,
        )

        logger.info("Corpus-grounded RetrieverQueryEngine configured")
        return query_engine

    except Exception as e:
        logger.error(f"Failed to create query engine: {type(e).__name__}: {e}")
        raise
