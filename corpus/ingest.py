import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

CORPUS_ROOT = Path("data") / "corpus"
CLASSIFIED_PATH = CORPUS_ROOT / "classified.jsonl"
INGEST_CHECKPOINT_PATH = CORPUS_ROOT / "ingest_checkpoint.json"
COLLECTION_NAME = "redlib"
UPSERT_BATCH_SIZE = 400
RATE_LIMIT_RETRY_DELAY_SECONDS = 60
MAX_RATE_LIMIT_RETRIES = 3


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        text = payload["text"]
        classification = payload["classification"]
    except KeyError as error:
        raise SystemExit(
            f"Classified record at line {line_number} is missing key: {error}"
        ) from error

    if not all(
        [
            isinstance(prompt_id, str) and prompt_id.strip(),
            isinstance(source, str) and source.strip(),
            isinstance(text, str) and text.strip(),
            isinstance(classification, dict),
        ]
    ):
        raise SystemExit(
            f"Classified record at line {line_number} has invalid field types."
        )

    primary_category = classification.get("primary_category")
    if not isinstance(primary_category, str) or not primary_category.strip():
        raise SystemExit(
            f"Classified record at line {line_number} has invalid "
            "classification.primary_category."
        )

    if "subtechnique" in classification:
        raise SystemExit(
            f"Classified record at line {line_number} still contains "
            "classification.subtechnique. Ingestion expects the cleaned final corpus."
        )

    return payload


def iter_classified_records(after_prompt_id: str | None = None) -> Iterator[dict[str, Any]]:
    ensure_classified_corpus_exists()

    resume_ready = after_prompt_id is None

    with CLASSIFIED_PATH.open("r", encoding="utf-8") as classified_file:
        for line_number, line in enumerate(classified_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
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

            record = load_classified_record(payload, line_number)

            if not resume_ready:
                if record["prompt_id"] == after_prompt_id:
                    resume_ready = True
                continue

            yield record

    if after_prompt_id is not None and not resume_ready:
        raise SystemExit(
            "Ingestion checkpoint refers to prompt_id "
            f"{after_prompt_id!r}, but that prompt_id was not found in "
            "data/corpus/classified.jsonl."
        )


def count_classified_records() -> int:
    count = 0
    for _ in iter_classified_records():
        count += 1

    if count == 0:
        raise SystemExit("Classified corpus is empty; cannot run ingestion.")
    return count


def load_checkpoint() -> dict[str, Any] | None:
    if not INGEST_CHECKPOINT_PATH.exists():
        return None

    with INGEST_CHECKPOINT_PATH.open("r", encoding="utf-8") as checkpoint_file:
        payload = json.load(checkpoint_file)

    if not isinstance(payload, dict):
        raise SystemExit("Ingestion checkpoint is malformed.")

    last_ingested_prompt_id = payload.get("last_ingested_prompt_id")
    records_ingested = payload.get("records_ingested")
    total_records = payload.get("total_records")
    timestamp = payload.get("timestamp")

    if last_ingested_prompt_id is not None and not isinstance(last_ingested_prompt_id, str):
        raise SystemExit("Ingestion checkpoint has invalid last_ingested_prompt_id.")
    if not isinstance(records_ingested, int) or records_ingested < 0:
        raise SystemExit("Ingestion checkpoint has invalid records_ingested.")
    if not isinstance(total_records, int) or total_records < 0:
        raise SystemExit("Ingestion checkpoint has invalid total_records.")
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise SystemExit("Ingestion checkpoint has invalid timestamp.")

    return payload


def save_checkpoint(
    *,
    last_ingested_prompt_id: str,
    records_ingested: int,
    total_records: int,
) -> None:
    payload = {
        "last_ingested_prompt_id": last_ingested_prompt_id,
        "records_ingested": records_ingested,
        "total_records": total_records,
        "timestamp": now_utc_iso(),
    }
    INGEST_CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INGEST_CHECKPOINT_PATH.open("w", encoding="utf-8", newline="\n") as checkpoint_file:
        json.dump(payload, checkpoint_file, indent=2, ensure_ascii=False)
        checkpoint_file.write("\n")


def resolve_resume_state(checkpoint: dict[str, Any] | None, total_records: int) -> tuple[str | None, int]:
    if checkpoint is None:
        return None, 0

    last_ingested_prompt_id = checkpoint.get("last_ingested_prompt_id")
    if last_ingested_prompt_id is None:
        return None, 0

    records_seen = 0
    for record in iter_classified_records():
        records_seen += 1
        if record["prompt_id"] == last_ingested_prompt_id:
            if records_seen > total_records:
                raise SystemExit("Checkpoint points beyond the classified corpus length.")
            return last_ingested_prompt_id, records_seen

    raise SystemExit(
        "Ingestion checkpoint refers to prompt_id "
        f"{last_ingested_prompt_id!r}, but that prompt_id was not found in "
        "data/corpus/classified.jsonl."
    )


def build_node(record: dict[str, Any]) -> Any:
    from llama_index.core.schema import TextNode

    node_id = make_node_id(record["prompt_id"])

    return TextNode(
        text=record["text"],
        metadata={
            "source": record["source"],
            "technique": record["classification"]["primary_category"],
            "prompt_id": record["prompt_id"],
        },
        excluded_embed_metadata_keys=["source", "technique", "prompt_id"],
        excluded_llm_metadata_keys=["source", "technique", "prompt_id"],
        id_=node_id,
    )


def make_node_id(prompt_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, prompt_id))


def get_ingest_vector_store() -> tuple[Any, Any]:
    from qdrant_client import QdrantClient
    from llama_index.vector_stores.qdrant import QdrantVectorStore

    try:
        client = QdrantClient(
            url=os.environ["QDRANT_URL"],
            api_key=os.environ["QDRANT_API_KEY"],
            timeout=180,
        )
    except KeyError as error:
        raise SystemExit(
            f"Missing required environment variable for ingestion: {error}"
        ) from error

    vector_store = QdrantVectorStore(
        client=client,
        collection_name="redlib",
        enable_hybrid=True,
        dense_vector_name="dense",
        sparse_vector_name="sparse",
    )
    return vector_store, client


def filter_already_ingested_records(
    client: Any,
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    if not records:
        return [], 0

    point_id_by_prompt_id = {
        record["prompt_id"]: make_node_id(record["prompt_id"])
        for record in records
    }

    existing_points = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=list(point_id_by_prompt_id.values()),
        with_payload=False,
        with_vectors=False,
    )
    existing_ids = {str(point.id) for point in existing_points}

    records_to_insert = [
        record
        for record in records
        if point_id_by_prompt_id[record["prompt_id"]] not in existing_ids
    ]
    skipped_count = len(records) - len(records_to_insert)
    return records_to_insert, skipped_count


def ensure_collection_exists(client: Any) -> None:
    from qdrant_client.models import (
        Distance,
        SparseIndexParams,
        SparseVectorParams,
        VectorParams,
    )

    if client.collection_exists(COLLECTION_NAME):
        logger.info("Collection %s already exists", COLLECTION_NAME)
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": VectorParams(size=1536, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(index=SparseIndexParams()),
        },
    )
    logger.info("Created collection %s", COLLECTION_NAME)


def ensure_keyword_payload_index(client: Any, field_name: str) -> None:
    from qdrant_client.http.models import PayloadSchemaType

    collection_info = client.get_collection(COLLECTION_NAME)
    payload_schema = collection_info.payload_schema or {}

    if field_name in payload_schema:
        logger.info("Qdrant payload index already exists for %s", field_name)
        return

    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name=field_name,
        field_schema=PayloadSchemaType.KEYWORD,
    )
    logger.info("Created Qdrant keyword payload index for %s", field_name)


def build_index(vector_store: Any, embed_model: Any) -> Any:
    from llama_index.core import StorageContext, VectorStoreIndex

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex([], storage_context=storage_context, embed_model=embed_model)


def is_rate_limit_error(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    if status_code == 429:
        return True

    response = getattr(error, "response", None)
    if getattr(response, "status_code", None) == 429:
        return True

    cause = getattr(error, "__cause__", None)
    if cause is not None and cause is not error:
        return is_rate_limit_error(cause)

    message = str(error).lower()
    return "429" in message or "rate limit" in message


def insert_batch_with_retries(index: Any, batch_nodes: list[Any], batch_number: int) -> None:
    attempt = 0
    while True:
        try:
            index.insert_nodes(batch_nodes)
            return
        except Exception as error:
            attempt += 1
            if not is_rate_limit_error(error) or attempt > MAX_RATE_LIMIT_RETRIES:
                logger.error(
                    "Failed to ingest batch %s after %s attempt(s): %s: %s",
                    batch_number,
                    attempt,
                    type(error).__name__,
                    error,
                )
                raise

            logger.warning(
                "OpenAI rate limit on batch %s (attempt %s/%s). Waiting %s seconds "
                "before retrying.",
                batch_number,
                attempt,
                MAX_RATE_LIMIT_RETRIES,
                RATE_LIMIT_RETRY_DELAY_SECONDS,
            )
            time.sleep(RATE_LIMIT_RETRY_DELAY_SECONDS)


def run_ingestion() -> None:
    from api.embedder import get_embed_model

    ensure_classified_corpus_exists()

    started_at = time.perf_counter()
    total_records = count_classified_records()
    checkpoint = load_checkpoint()
    resume_prompt_id, records_ingested = resolve_resume_state(checkpoint, total_records)

    if records_ingested > total_records:
        raise SystemExit(
            "Ingestion checkpoint records_ingested exceeds the number of classified records."
        )

    logger.info(
        "Starting ingestion over %s classified records; resuming after prompt_id=%s",
        total_records,
        resume_prompt_id,
    )

    embed_model = get_embed_model()
    vector_store, client = get_ingest_vector_store()
    ensure_collection_exists(client)
    ensure_keyword_payload_index(client, "prompt_id")
    ensure_keyword_payload_index(client, "technique")
    index = build_index(vector_store, embed_model)

    batch_records: list[dict[str, Any]] = []
    last_prompt_id: str | None = None
    total_batches = 0
    resume_mode = resume_prompt_id is not None

    for record in iter_classified_records(after_prompt_id=resume_prompt_id):
        batch_records.append(record)
        last_prompt_id = record["prompt_id"]

        if len(batch_records) < UPSERT_BATCH_SIZE:
            continue

        records_to_insert = batch_records
        skipped_records = 0
        if resume_mode:
            records_to_insert, skipped_records = filter_already_ingested_records(
                client,
                batch_records,
            )
            if skipped_records:
                logger.warning(
                    "Skipped %s already-ingested resumed records before batch %s upsert.",
                    skipped_records,
                    total_batches + 1,
                )

        if not records_to_insert:
            if last_prompt_id is None:
                raise SystemExit("Resume skip path reached a batch without a prompt_id.")
            records_ingested += skipped_records
            save_checkpoint(
                last_ingested_prompt_id=last_prompt_id,
                records_ingested=records_ingested,
                total_records=total_records,
            )
            batch_records = []
            continue

        batch_nodes = [build_node(batch_record) for batch_record in records_to_insert]
        total_batches += 1
        insert_batch_with_retries(index, batch_nodes, total_batches)
        records_ingested += len(batch_records)
        save_checkpoint(
            last_ingested_prompt_id=last_prompt_id,
            records_ingested=records_ingested,
            total_records=total_records,
        )
        progress_percent = (records_ingested / total_records) * 100
        print(
            f"Ingested {records_ingested}/{total_records} records "
            f"({progress_percent:.1f}%) - batch {total_batches} complete"
        )
        batch_records = []

    if batch_records:
        records_to_insert = batch_records
        skipped_records = 0
        if resume_mode:
            records_to_insert, skipped_records = filter_already_ingested_records(
                client,
                batch_records,
            )
            if skipped_records:
                logger.warning(
                    "Skipped %s already-ingested resumed records before final batch upsert.",
                    skipped_records,
                )

        total_batches += 1
        if not records_to_insert:
            if last_prompt_id is None:
                raise SystemExit("Resume skip path reached a final batch without a prompt_id.")
            records_ingested += skipped_records
            save_checkpoint(
                last_ingested_prompt_id=last_prompt_id,
                records_ingested=records_ingested,
                total_records=total_records,
            )
            total_batches -= 1
        else:
            batch_nodes = [build_node(batch_record) for batch_record in records_to_insert]
            insert_batch_with_retries(index, batch_nodes, total_batches)
            records_ingested += len(batch_records)
            if last_prompt_id is None:
                raise SystemExit("Ingestion completed a final batch without a prompt_id.")
            save_checkpoint(
                last_ingested_prompt_id=last_prompt_id,
                records_ingested=records_ingested,
                total_records=total_records,
            )
            progress_percent = (records_ingested / total_records) * 100
            print(
                f"Ingested {records_ingested}/{total_records} records "
                f"({progress_percent:.1f}%) - batch {total_batches} complete"
            )

    runtime_seconds = time.perf_counter() - started_at
    print(f"Total records ingested: {records_ingested}")
    print(f"Total batches: {total_batches}")
    print(f"Runtime: {runtime_seconds:.2f} seconds")
    print(f"Collection: {COLLECTION_NAME}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    run_ingestion()
