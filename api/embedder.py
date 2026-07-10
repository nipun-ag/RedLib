import os
import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_embed_model() -> Any:
    """Configure and return OpenAI embedding model.

    Raises:
        ValueError: If OPENAI_API_KEY environment variable is not set

    Returns:
        Configured OpenAIEmbedding instance for text-embedding-3-small
    """
    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        error_msg = "OPENAI_API_KEY environment variable not set"
        logger.error(error_msg)
        raise ValueError(error_msg)

    try:
        from llama_index.embeddings.openai import OpenAIEmbedding
    except ImportError as error:
        raise ImportError(
            "llama_index is required to configure embeddings. "
            "Install project dependencies before running the API or ingestion pipeline."
        ) from error

    embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        dimensions=1536,
        api_key=api_key,
    )

    logger.info("OpenAI embedding model configured: text-embedding-3-small (1536 dims)")
    return embed_model
