import os
import logging
import hashlib
import json
import time
from typing import Any
import tiktoken
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, SparseVectorParams, SparseIndexParams
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import MetadataMode, TextNode

from data_loader import load_all_datasets
from classifier import classify_batch, classify_with_timeout
from embedder import get_embed_model

logger = logging.getLogger(__name__)

CHECKPOINT_FILE = "ingest_checkpoint.json"
MAX_EMBED_TOKENS = 8000
EMBED_MODEL_NAME = "text-embedding-3-small"
EMBED_ENCODING = tiktoken.encoding_for_model(EMBED_MODEL_NAME)


def get_qdrant_client() -> QdrantClient:
    """Connect to Qdrant Cloud and return a QdrantClient.

    Raises:
        ValueError: If QDRANT_URL or QDRANT_API_KEY not set

    Returns:
        QdrantClient
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
        client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=120,
        )
        logger.info("Connected to Qdrant Cloud")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {type(e).__name__}: {e}")
        raise


def generate_id(source: str, text: str) -> str:
    """Generate a unique stable ID for a prompt.

    Args:
        source: Dataset source name
        text: Prompt text

    Returns:
        ID in format "{source}__{hash}" where hash is first 8 chars of MD5
    """
    text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
    return f"{source}__{text_hash}"


def count_tokens(text: str) -> int:
    """Count tokens for the embedding model tokenizer."""
    return len(EMBED_ENCODING.encode(text))


def save_checkpoint(classified_records: list[dict], last_index: int) -> None:
    """Save classification progress to checkpoint file.

    Args:
        classified_records: List of classified prompt records
        last_index: Index of the last classified prompt
    """
    checkpoint_data = {
        "classified": classified_records,
        "last_index": last_index,
    }
    try:
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump(checkpoint_data, f)
        logger.info(f"Saved checkpoint at index {last_index}")
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {type(e).__name__}: {e}")


def load_checkpoint() -> tuple[list[dict], int]:
    """Load classification progress from checkpoint file if it exists.

    Returns:
        Tuple of (classified_records, last_index). Returns ([], 0) if no checkpoint.
    """
    if not os.path.exists(CHECKPOINT_FILE):
        return [], 0

    try:
        with open(CHECKPOINT_FILE, "r") as f:
            checkpoint_data = json.load(f)
        classified = checkpoint_data.get("classified", [])
        last_index = checkpoint_data.get("last_index", 0)
        logger.info(f"Loaded checkpoint: {len(classified)} records, last_index={last_index}")
        return classified, last_index
    except Exception as e:
        logger.error(f"Failed to load checkpoint: {type(e).__name__}: {e}")
        return [], 0


def run_ingestion() -> None:
    """Run the complete ingestion pipeline."""
    try:
        # Step 1: Load all datasets
        logger.info("Step 1: Loading datasets...")
        all_records = load_all_datasets()
        logger.info(f"Loaded {len(all_records)} records")

        # Step 2: Check for checkpoint and resume if available
        logger.info("Step 2: Checking for checkpoint...")
        classified_records, last_index = load_checkpoint()

        if last_index > 0:
            logger.info(f"Resuming from checkpoint at index {last_index}/{len(all_records)}")
            records = classified_records
            start_idx = last_index
        else:
            records = []
            start_idx = 0

        # Step 3: Classify prompts with checkpoint saving
        logger.info("Step 3: Classifying prompts...")
        for idx in range(start_idx, len(all_records)):
            prompt_dict = all_records[idx]
            text = prompt_dict["text"]

            technique = classify_with_timeout(text)
            result = prompt_dict.copy()
            result["technique"] = technique

            records.append(result)

            # Save checkpoint every 100 prompts
            if (idx + 1) % 100 == 0:
                save_checkpoint(records, idx + 1)
                logger.info(f"Classified {idx + 1} / {len(all_records)} prompts")

            # Delay to avoid rate limiting
            time.sleep(0.5)

        logger.info("Classification complete")

        # Step 4: Get embedding model
        logger.info("Step 4: Configuring embedding model...")
        embed_model = get_embed_model()

        # Step 5: Connect to Qdrant
        logger.info("Step 5: Connecting to Qdrant...")
        client = get_qdrant_client()

        # Step 6: Create collection if it doesn't exist
        logger.info("Step 6: Ensuring collection exists...")
        collection_name = "redlib"

        if not client.collection_exists(collection_name):
            try:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "dense": VectorParams(size=1536, distance=Distance.COSINE)
                    },
                    sparse_vectors_config={
                        "sparse": SparseVectorParams(index=SparseIndexParams())
                    },
                )
                logger.info(f"Created collection: {collection_name}")
            except Exception as e:
                logger.error(
                    f"Failed to create collection: {type(e).__name__}: {e}"
                )
                raise
        else:
            logger.info(f"Collection {collection_name} already exists")

        # Step 7: Build vector store and index
        logger.info("Step 7: Building vector store...")
        vector_store = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            enable_hybrid=True,
            dense_vector_name="dense",
            sparse_vector_name="sparse",
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents([], storage_context=storage_context)

        # Step 8: Build nodes and upsert
        logger.info("Step 8: Upserting nodes to Qdrant...")
        nodes = []

        for record in records:
            text = record["text"]
            source = record["source"]
            technique = record["technique"]

            # Generate ID
            vector_id = generate_id(source, text)
            prompt_id = vector_id.split("__")[1]

            # Build metadata
            metadata = {
                "source": source,
                "technique": technique,
                "prompt_id": prompt_id,
            }

            # Create node
            node = TextNode(
                text=text,
                id=vector_id,
                metadata=metadata,
            )
            raw_token_count = count_tokens(text)
            embed_text = node.get_content(metadata_mode=MetadataMode.EMBED)
            embed_token_count = count_tokens(embed_text)

            logger.info(
                f"Preparing prompt_id={prompt_id} "
                f"source={source} "
                f"raw_chars={len(text)} "
                f"raw_tokens={raw_token_count} "
                f"embed_chars={len(embed_text)} "
                f"embed_tokens={embed_token_count}"
            )

            if embed_text != text:
                logger.info(
                    f"Embedded content differs for prompt_id={prompt_id} "
                    f"source={source} "
                    f"extra_chars={len(embed_text) - len(text)} "
                    f"extra_tokens={embed_token_count - raw_token_count}"
                )
            if embed_token_count > MAX_EMBED_TOKENS:
                logger.warning(
                    f"Skipping oversized prompt "
                    f"prompt_id={prompt_id} "
                    f"source={source} "
                    f"chars={len(embed_text)} "
                    f"tokens={embed_token_count}"
                )
                continue
            nodes.append(node)

            # Upsert when batch reaches 100
            if len(nodes) >= 20:
                try:
                    logger.info(f"About to insert batch of {len(nodes)} nodes")
                    index.insert_nodes(nodes)
                    logger.info(f"Successfully inserted batch of {len(nodes)} nodes")
                    nodes = []
                except Exception as e:
                    logger.error(
                        f"Failed to upsert batch of {len(nodes)} nodes: "
                        f"{type(e).__name__}: {e}"
                    )
                    raise

        # Upsert remaining nodes
        if nodes:
            try:
                logger.info(f"About to insert batch of {len(nodes)} nodes")
                index.insert_nodes(nodes)
                logger.info(f"Successfully inserted batch of {len(nodes)} nodes")
            except Exception as e:
                logger.error(
                    f"Failed to upsert batch of {len(nodes)} nodes: "
                    f"{type(e).__name__}: {e}"
                )
                raise

        logger.info(f"Ingestion complete. Total records ingested: {len(records)}")

        # Clean up checkpoint file after successful completion
        if os.path.exists(CHECKPOINT_FILE):
            try:
                os.remove(CHECKPOINT_FILE)
                logger.info("Removed checkpoint file after successful ingestion")
            except Exception as e:
                logger.warning(f"Failed to remove checkpoint file: {type(e).__name__}: {e}")

    except Exception as e:
        logger.error(f"Ingestion failed: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    run_ingestion()
