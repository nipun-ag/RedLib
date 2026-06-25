import os
import logging
from typing import Optional
from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.schema import NodeWithScore
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.postprocessor.cohere_rerank import CohereRerank
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


def get_vector_store():
    """Connect to Qdrant Cloud and return a QdrantVectorStore.

    Reads QDRANT_URL and QDRANT_API_KEY from environment variables.

    Raises:
        ValueError: If QDRANT_URL or QDRANT_API_KEY is not set

    Returns:
        QdrantVectorStore configured for hybrid search
    """
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

    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        vector_store = QdrantVectorStore(
            client=client,
            collection_name="redlib",
            enable_hybrid=True,
            dense_vector_name="dense",
            sparse_vector_name="sparse",
        )
        logger.info("Connected to Qdrant Cloud, collection: redlib")
        return vector_store
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {type(e).__name__}: {e}")
        raise


def get_retriever(embed_model, top_k: int = 20):
    """Configure hybrid retriever with dense + sparse search and RRF.

    Args:
        embed_model: Configured OpenAIEmbedding object
        top_k: Number of results to retrieve from each search type

    Returns:
        Configured QueryFusionRetriever
    """
    # Get vector store (Qdrant Cloud with hybrid search)
    vector_store = get_vector_store()

    # Create VectorStoreIndex
    index_obj = VectorStoreIndex.from_vector_store(
        vector_store=vector_store, embed_model=embed_model
    )

    # Create dense retriever
    dense_retriever = VectorIndexRetriever(
        index=index_obj, similarity_top_k=top_k
    )

    # Create sparse retriever using Pinecone's BM25
    sparse_retriever = vector_store.as_retriever(similarity_top_k=top_k)

    # Combine into QueryFusionRetriever with RRF
    retriever = QueryFusionRetriever(
        retrievers=[dense_retriever, sparse_retriever],
        mode="reciprocal_rerank",
        num_queries=1,
        use_async=False,
    )

    logger.info(f"QueryFusionRetriever configured with top_k={top_k}")
    return retriever


def get_reranker(top_n: int = 5) -> CohereRerank:
    """Configure Cohere reranker postprocessor.

    Args:
        top_n: Number of results to keep after reranking

    Returns:
        Configured CohereRerank postprocessor

    Raises:
        ValueError: If COHERE_API_KEY is not set
    """
    api_key = os.environ.get("COHERE_API_KEY")

    if not api_key:
        error_msg = "COHERE_API_KEY environment variable not set"
        logger.error(error_msg)
        raise ValueError(error_msg)

    reranker = CohereRerank(
        model="rerank-english-v3.0",
        top_n=top_n,
        api_key=api_key,
    )

    logger.info(f"CohereRerank configured with top_n={top_n}")
    return reranker


def retrieve(
    query: str,
    retriever,
    reranker,
    category_filter: Optional[str] = None,
) -> list[NodeWithScore]:
    """Run hybrid retrieval + reranking pipeline.

    Args:
        query: Query string
        retriever: Configured QueryFusionRetriever
        reranker: Configured CohereRerank postprocessor
        category_filter: Optional technique category to filter by

    Returns:
        List of reranked nodes, empty list on error
    """
    try:
        # Build metadata filter if category provided
        if category_filter:
            filters = MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="technique",
                        value=category_filter,
                        operator=FilterOperator.EQ,
                    )
                ]
            )
        else:
            filters = None

        # Run retriever
        retrieved_nodes = retriever.retrieve(query, filters=filters)
        logger.info(
            f"Retrieved {len(retrieved_nodes)} results for query: {query[:50]}..."
        )

        # Apply reranker
        reranked_nodes = reranker.postprocess_nodes(
            nodes=retrieved_nodes,
            query_str=query,
        )
        logger.info(f"Reranked to {len(reranked_nodes)} results")

        return reranked_nodes

    except Exception as e:
        logger.error(f"Retrieval failed: {type(e).__name__}: {e}")
        return []
