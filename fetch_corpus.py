import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from datasets import load_dataset

logger = logging.getLogger(__name__)

CORPUS_ROOT = Path("data") / "corpus"
RAW_ROOT = CORPUS_ROOT / "raw"
RAW_STAGING_ROOT = CORPUS_ROOT / "raw_staging"


@dataclass(frozen=True)
class SnapshotSpec:
    split: str
    config: str | None = None
    output_name: str | None = None


@dataclass(frozen=True)
class DatasetSpec:
    source_name: str
    dataset_id: str
    snapshots: tuple[SnapshotSpec, ...]


DATASET_REGISTRY: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        source_name="trustairlab",
        dataset_id="TrustAIRLab/in-the-wild-jailbreak-prompts",
        snapshots=(
            SnapshotSpec(
                config="jailbreak_2023_05_07",
                split="train",
                output_name="jailbreak_2023_05_07_train",
            ),
            SnapshotSpec(
                config="jailbreak_2023_12_25",
                split="train",
                output_name="jailbreak_2023_12_25_train",
            ),
        ),
    ),
    DatasetSpec(
        source_name="rubend18",
        dataset_id="rubend18/ChatGPT-Jailbreak-Prompts",
        snapshots=(SnapshotSpec(split="train"),),
    ),
    DatasetSpec(
        source_name="jackhhao",
        dataset_id="jackhhao/jailbreak-classification",
        snapshots=(
            SnapshotSpec(split="train"),
            SnapshotSpec(split="test"),
        ),
    ),
    DatasetSpec(
        source_name="harmbench",
        dataset_id="swiss-ai/harmbench",
        snapshots=(
            SnapshotSpec(
                config="HumanJailbreaks",
                split="val",
                output_name="HumanJailbreaks_val",
            ),
            SnapshotSpec(
                config="HumanJailbreaks",
                split="test",
                output_name="HumanJailbreaks_test",
            ),
        ),
    ),
)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def get_huggingface_token() -> str | None:
    token = os.environ.get("HUGGINGFACE_TOKEN")
    if token:
        logger.info("Using HUGGINGFACE_TOKEN for authenticated dataset access")
    else:
        logger.info("No HUGGINGFACE_TOKEN found; attempting anonymous dataset access")
    return token


def snapshot_label(snapshot: SnapshotSpec) -> str:
    if snapshot.output_name:
        return snapshot.output_name

    parts = []
    if snapshot.config:
        parts.append(snapshot.config)
    parts.append(snapshot.split)
    return "_".join(parts)


def serialize_record(record: dict[str, Any]) -> str:
    # Preserving the original field values lets later audit stages inspect
    # upstream quality issues without this stage mutating the source data.
    return json.dumps(record, ensure_ascii=False)


def write_jsonl(records: Any, output_path: Path) -> int:
    record_count = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for record in records:
            output_file.write(serialize_record(dict(record)))
            output_file.write("\n")
            record_count += 1
    return record_count


def fetch_snapshot(
    dataset_spec: DatasetSpec,
    snapshot_spec: SnapshotSpec,
    source_dir: Path,
    hf_token: str | None,
    fetch_timestamp: str,
) -> dict[str, Any]:
    label = snapshot_label(snapshot_spec)
    output_path = source_dir / f"{label}.jsonl"

    logger.info(
        "Fetching dataset '%s' (config=%s, split=%s)",
        dataset_spec.dataset_id,
        snapshot_spec.config,
        snapshot_spec.split,
    )

    dataset = load_dataset(
        dataset_spec.dataset_id,
        snapshot_spec.config,
        split=snapshot_spec.split,
        trust_remote_code=False,
        token=hf_token,
    )
    record_count = write_jsonl(dataset, output_path)

    logger.info(
        "Snapshotted %s records for source '%s' into %s",
        record_count,
        dataset_spec.source_name,
        output_path,
    )

    return {
        "source_name": dataset_spec.source_name,
        "dataset_identifier": dataset_spec.dataset_id,
        "config": snapshot_spec.config,
        "split": snapshot_spec.split,
        "fetch_timestamp": fetch_timestamp,
        "record_count": record_count,
        "output_file": output_path.name,
    }


def write_source_metadata(source_dir: Path, metadata: dict[str, Any]) -> None:
    metadata_path = source_dir / "fetch_metadata.json"
    with metadata_path.open("w", encoding="utf-8", newline="\n") as metadata_file:
        json.dump(metadata, metadata_file, indent=2, ensure_ascii=False)
        metadata_file.write("\n")


def snapshot_dataset(
    dataset_spec: DatasetSpec,
    raw_root: Path,
    hf_token: str | None,
    fetch_timestamp: str,
) -> dict[str, Any]:
    source_dir = raw_root / dataset_spec.source_name
    source_dir.mkdir(parents=True, exist_ok=True)

    snapshots_metadata = []
    total_records = 0

    for snapshot_spec in dataset_spec.snapshots:
        snapshot_metadata = fetch_snapshot(
            dataset_spec=dataset_spec,
            snapshot_spec=snapshot_spec,
            source_dir=source_dir,
            hf_token=hf_token,
            fetch_timestamp=fetch_timestamp,
        )
        snapshots_metadata.append(snapshot_metadata)
        total_records += snapshot_metadata["record_count"]

    source_metadata = {
        "source_name": dataset_spec.source_name,
        "dataset_identifier": dataset_spec.dataset_id,
        "fetch_timestamp": fetch_timestamp,
        "total_record_count": total_records,
        "snapshots": snapshots_metadata,
    }
    write_source_metadata(source_dir, source_metadata)

    return source_metadata


def prepare_staging_root() -> Path:
    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)

    if RAW_STAGING_ROOT.exists():
        shutil.rmtree(RAW_STAGING_ROOT)

    RAW_STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    return RAW_STAGING_ROOT


def replace_raw_snapshot(staging_root: Path) -> None:
    if RAW_ROOT.exists():
        shutil.rmtree(RAW_ROOT)
    staging_root.replace(RAW_ROOT)


def fetch_all_datasets() -> list[dict[str, Any]]:
    fetch_timestamp = datetime.now(timezone.utc).isoformat()
    hf_token = get_huggingface_token()
    staging_root = prepare_staging_root()

    source_summaries = []
    try:
        for dataset_spec in DATASET_REGISTRY:
            source_summaries.append(
                snapshot_dataset(
                    dataset_spec=dataset_spec,
                    raw_root=staging_root,
                    hf_token=hf_token,
                    fetch_timestamp=fetch_timestamp,
                )
            )
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise

    replace_raw_snapshot(staging_root)
    return source_summaries


def main() -> int:
    configure_logging()
    summaries = fetch_all_datasets()
    total_records = sum(summary["total_record_count"] for summary in summaries)
    logger.info(
        "Completed raw corpus snapshot for %s sources with %s total records",
        len(summaries),
        total_records,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
