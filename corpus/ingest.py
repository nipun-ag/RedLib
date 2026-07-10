import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CORPUS_ROOT = Path("data") / "corpus"
CLASSIFIED_PATH = CORPUS_ROOT / "classified_clean.jsonl"
INGEST_CHECKPOINT_PATH = CORPUS_ROOT / "ingest_checkpoint.json"
COLLECTION_NAME = "redlib"
UPSERT_BATCH_SIZE = 20


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_file_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_qdrant_client() -> Any:
    """Connect to Qdrant Cloud and return a QdrantClient."""
    from qdrant_client import QdrantClient

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
    except Exception as error:
        logger.error(
            "Failed to connect to Qdrant: %s: %s",
            type(error).__name__,
            error,
        )
        raise


def ensure_prompt_id_payload_index(
    client: Any,
    collection_name: str,
) -> None:
    """Ensure prompt_id is indexed for direct Qdrant payload filtering."""
    from qdrant_client.http.models import PayloadSchemaType

    collection_info = client.get_collection(collection_name)
    payload_schema = collection_info.payload_schema or {}

    if "prompt_id" in payload_schema:
        logger.info("Qdrant payload index already exists for prompt_id")
        return

    client.create_payload_index(
        collection_name=collection_name,
        field_name="prompt_id",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    logger.info("Created Qdrant keyword payload index for prompt_id")


def ensure_collection_exists(client: Any, collection_name: str) -> None:
    from qdrant_client.models import (
        Distance,
        SparseIndexParams,
        SparseVectorParams,
        VectorParams,
    )

    if client.collection_exists(collection_name):
        logger.info("Collection %s already exists", collection_name)
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": VectorParams(size=1536, distance=Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(index=SparseIndexParams())
        },
    )
    logger.info("Created collection %s", collection_name)


def count_classified_records() -> int:
    ensure_classified_corpus_exists()

    count = 0
    with CLASSIFIED_PATH.open("r", encoding="utf-8") as classified_file:
        for line in classified_file:
            if line.strip():
                count += 1

    if count == 0:
        raise SystemExit("Classified corpus is empty; cannot run ingestion.")
    return count


def ensure_classified_corpus_exists() -> None:
    if CLASSIFIED_PATH.exists():
        return
    raise SystemExit(
        "Classified corpus not found at data/corpus/classified.jsonl. "
        "Run python -m corpus.classify_corpus before python -m corpus.ingest."
    )


def load_classified_record(payload: dict[str, Any], line_number: int) -> dict[str, Any]:
    try:
        prompt_id = payload["prompt_id"]
        source = payload["source"]
        source_file = payload["source_file"]
        source_row = payload["source_row"]
        text = payload["text"]
        raw_fields = payload["raw_fields"]
        classification = payload["classification"]
    except KeyError as error:
        raise SystemExit(
            f"Classified record at line {line_number} is missing key: {error}"
        ) from error

    if not all(
        [
            isinstance(prompt_id, str),
            isinstance(source, str),
            isinstance(source_file, str),
            isinstance(source_row, int),
            isinstance(text, str),
            isinstance(raw_fields, dict),
            isinstance(classification, dict),
        ]
    ):
        raise SystemExit(
            f"Classified record at line {line_number} has invalid field types."
        )

    primary_category = classification.get("primary_category")
    supporting_traits = classification.get("supporting_traits")
    confidence = classification.get("confidence")
    rationale = classification.get("rationale")

    if not isinstance(primary_category, str) or not primary_category.strip():
        raise SystemExit(
            f"Classified record at line {line_number} has invalid classification.primary_category."
        )
    if not isinstance(supporting_traits, list):
        raise SystemExit(
            f"Classified record at line {line_number} has invalid classification.supporting_traits."
        )
    if not isinstance(confidence, (int, float)):
        raise SystemExit(
            f"Classified record at line {line_number} has invalid classification.confidence."
        )
    if not isinstance(rationale, str):
        raise SystemExit(
            f"Classified record at line {line_number} has invalid classification.rationale."
        )

    return payload


def iter_classified_records(*, start_index: int = 0) -> Any:
    ensure_classified_corpus_exists()

    emitted = 0
    with CLASSIFIED_PATH.open("r", encoding="utf-8") as classified_file:
        for line_number, line in enumerate(classified_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue

            if emitted < start_index:
                emitted += 1
                continue

            try:
                payload = json.loads(stripped_line)
            except json.JSONDecodeError as error:
                raise SystemExit(
                    f"Malformed classified JSONL at line {line_number}: {error.msg}"
                ) from error

            if not isinstance(payload, dict):
                raise SystemExit(
                    f"Classified record at line {line_number} is not a JSON object."
                )

            yield load_classified_record(payload, line_number)
            emitted += 1


def load_checkpoint() -> dict[str, Any] | None:
    if not INGEST_CHECKPOINT_PATH.exists():
        return None

    with INGEST_CHECKPOINT_PATH.open("r", encoding="utf-8") as checkpoint_file:
        payload = json.load(checkpoint_file)

    if not isinstance(payload, dict):
        raise SystemExit("Ingestion checkpoint is malformed.")
    return payload


def save_checkpoint(payload: dict[str, Any]) -> None:
    INGEST_CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INGEST_CHECKPOINT_PATH.open(
        "w", encoding="utf-8", newline="\n"
    ) as checkpoint_file:
        json.dump(payload, checkpoint_file, indent=2, ensure_ascii=False)
        checkpoint_file.write("\n")


def remove_checkpoint_if_exists() -> None:
    if INGEST_CHECKPOINT_PATH.exists():
        INGEST_CHECKPOINT_PATH.unlink()


def prepare_run_state(
    *,
    total_records: int,
    classified_sha256: str,
) -> dict[str, Any]:
    checkpoint = load_checkpoint()
    if checkpoint is None:
        return {
            "run_started_at": now_utc_iso(),
            "classified_path": str(CLASSIFIED_PATH),
            "classified_sha256": classified_sha256,
            "total_records": total_records,
            "processed_records": 0,
            "last_updated_at": now_utc_iso(),
            "completed": False,
        }

    if checkpoint.get("classified_sha256") != classified_sha256:
        raise SystemExit(
            "Existing ingestion checkpoint does not match the current "
            "classified.jsonl. Delete data/corpus/ingest_checkpoint.json "
            "to start a fresh ingestion run."
        )

    checkpoint["total_records"] = total_records
    checkpoint["completed"] = False
    return checkpoint


def build_node(record: dict[str, Any]) -> Any:
    from llama_index.core.schema import TextNode

    classification = record["classification"]
    return TextNode(
        text=record["text"],
        id_=record["prompt_id"],
        metadata={
            "source": record["source"],
            "technique": classification["primary_category"],
            "prompt_id": record["prompt_id"],
        },
    )


def run_ingestion() -> None:
    from api.embedder import get_embed_model
    from llama_index.core import StorageContext, VectorStoreIndex
    from llama_index.vector_stores.qdrant import QdrantVectorStore

    ensure_classified_corpus_exists()

    total_records = count_classified_records()
    classified_sha256 = compute_file_sha256(CLASSIFIED_PATH)
    checkpoint = prepare_run_state(
        total_records=total_records,
        classified_sha256=classified_sha256,
    )

    processed_records = checkpoint.get("processed_records", 0)
    if not isinstance(processed_records, int) or processed_records < 0:
        raise SystemExit("Ingestion checkpoint has invalid processed_records.")
    if processed_records > total_records:
        raise SystemExit(
            "Ingestion checkpoint processed_records exceeds the number of "
            "classified records."
        )

    logger.info(
        "Starting ingestion over %s classified records; resuming at record %s",
        total_records,
        processed_records,
    )

    embed_model = get_embed_model()
    client = get_qdrant_client()
    ensure_collection_exists(client, COLLECTION_NAME)
    ensure_prompt_id_payload_index(client, COLLECTION_NAME)

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        enable_hybrid=True,
        dense_vector_name="dense",
        sparse_vector_name="sparse",
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(
        [],
        storage_context=storage_context,
        embed_model=embed_model,
    )

    batch_nodes: list[TextNode] = []
    for record in iter_classified_records(start_index=processed_records):
        batch_nodes.append(build_node(record))
        if len(batch_nodes) < UPSERT_BATCH_SIZE:
            continue

        index.insert_nodes(batch_nodes)
        processed_records += len(batch_nodes)
        checkpoint["processed_records"] = processed_records
        checkpoint["last_updated_at"] = now_utc_iso()
        save_checkpoint(checkpoint)
        logger.info(
            "Ingested %s/%s classified records",
            processed_records,
            total_records,
        )
        batch_nodes = []

    if batch_nodes:
        index.insert_nodes(batch_nodes)
        processed_records += len(batch_nodes)
        checkpoint["processed_records"] = processed_records
        checkpoint["last_updated_at"] = now_utc_iso()
        save_checkpoint(checkpoint)
        logger.info(
            "Ingested %s/%s classified records",
            processed_records,
            total_records,
        )

    if processed_records != total_records:
        raise SystemExit(
            f"Ingestion completed {processed_records} records but expected {total_records}."
        )

    checkpoint["completed"] = True
    checkpoint["last_updated_at"] = now_utc_iso()
    save_checkpoint(checkpoint)
    remove_checkpoint_if_exists()
    logger.info(
        "Ingestion complete. Embedded %s classified records into %s.",
        total_records,
        COLLECTION_NAME,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    run_ingestion()
