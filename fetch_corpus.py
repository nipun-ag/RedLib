import csv
import json
import logging
import os
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass, field
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
    output_name: str


@dataclass(frozen=True)
class HuggingFaceSnapshotSpec(SnapshotSpec):
    split: str
    config: str | None = None
    load_dataset_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GitHubRawSnapshotSpec(SnapshotSpec):
    url: str
    format_label: str


@dataclass(frozen=True)
class SourceSpec:
    source_name: str
    source_type: str
    snapshots: tuple[SnapshotSpec, ...]


@dataclass(frozen=True)
class HuggingFaceSourceSpec(SourceSpec):
    dataset_id: str


@dataclass(frozen=True)
class GitHubRawSourceSpec(SourceSpec):
    repository: str


SOURCE_REGISTRY: tuple[SourceSpec, ...] = (
    HuggingFaceSourceSpec(
        source_name="trustairlab",
        source_type="huggingface",
        dataset_id="TrustAIRLab/in-the-wild-jailbreak-prompts",
        snapshots=(
            HuggingFaceSnapshotSpec(
                config="jailbreak_2023_05_07",
                split="train",
                output_name="jailbreak_2023_05_07_train.jsonl",
            ),
            HuggingFaceSnapshotSpec(
                config="jailbreak_2023_12_25",
                split="train",
                output_name="jailbreak_2023_12_25_train.jsonl",
            ),
        ),
    ),
    HuggingFaceSourceSpec(
        source_name="rubend18",
        source_type="huggingface",
        dataset_id="rubend18/ChatGPT-Jailbreak-Prompts",
        snapshots=(
            HuggingFaceSnapshotSpec(
                split="train",
                output_name="train.jsonl",
            ),
        ),
    ),
    HuggingFaceSourceSpec(
        source_name="jackhhao",
        source_type="huggingface",
        dataset_id="jackhhao/jailbreak-classification",
        snapshots=(
            HuggingFaceSnapshotSpec(
                split="train",
                output_name="train.jsonl",
            ),
            HuggingFaceSnapshotSpec(
                split="test",
                output_name="test.jsonl",
            ),
        ),
    ),
    HuggingFaceSourceSpec(
        source_name="harmbench",
        source_type="huggingface",
        dataset_id="swiss-ai/harmbench",
        snapshots=(
            HuggingFaceSnapshotSpec(
                config="HumanJailbreaks",
                split="val",
                output_name="HumanJailbreaks_val.jsonl",
            ),
            HuggingFaceSnapshotSpec(
                config="HumanJailbreaks",
                split="test",
                output_name="HumanJailbreaks_test.jsonl",
            ),
        ),
    ),
    HuggingFaceSourceSpec(
        source_name="wildjailbreak",
        source_type="huggingface",
        dataset_id="allenai/wildjailbreak",
        snapshots=(
            HuggingFaceSnapshotSpec(
                config="train",
                split="train",
                output_name="train.jsonl",
                load_dataset_kwargs={
                    "delimiter": "\t",
                    "keep_default_na": False,
                },
            ),
            HuggingFaceSnapshotSpec(
                config="eval",
                split="train",
                output_name="eval.jsonl",
                load_dataset_kwargs={
                    "delimiter": "\t",
                    "keep_default_na": False,
                },
            ),
        ),
    ),
    HuggingFaceSourceSpec(
        source_name="jailbreakbench_behaviors",
        source_type="huggingface",
        dataset_id="JailbreakBench/JBB-Behaviors",
        snapshots=(
            HuggingFaceSnapshotSpec(
                config="behaviors",
                split="harmful",
                output_name="behaviors_harmful.jsonl",
            ),
        ),
    ),
    GitHubRawSourceSpec(
        source_name="advbench",
        source_type="github_raw",
        repository="llm-attacks/llm-attacks",
        snapshots=(
            GitHubRawSnapshotSpec(
                url="https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/data/advbench/harmful_behaviors.csv",
                output_name="harmful_behaviors.csv",
                format_label="csv",
            ),
        ),
    ),
    HuggingFaceSourceSpec(
        source_name="maliciousinstruct",
        source_type="huggingface",
        dataset_id="walledai/MaliciousInstruct",
        snapshots=(
            HuggingFaceSnapshotSpec(
                config="default",
                split="train",
                output_name="train.jsonl",
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
        logger.info("Using HUGGINGFACE_TOKEN for authenticated Hugging Face dataset access")
    else:
        logger.info("No HUGGINGFACE_TOKEN found; attempting anonymous Hugging Face dataset access")
    return token


def serialize_record(record: dict[str, Any]) -> str:
    # Raw snapshots must preserve source field values exactly so later
    # audit and normalization stages can inspect upstream data as fetched.
    return json.dumps(record, ensure_ascii=False)


def write_jsonl(records: Any, output_path: Path) -> int:
    record_count = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for record in records:
            output_file.write(serialize_record(dict(record)))
            output_file.write("\n")
            record_count += 1
    return record_count


def write_raw_bytes(output_path: Path, payload: bytes) -> int:
    with output_path.open("wb") as output_file:
        output_file.write(payload)
    return len(payload)


def count_csv_rows(payload: bytes) -> int | None:
    try:
        decoded_payload = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None

    reader = csv.reader(decoded_payload.splitlines())
    row_count = sum(1 for _ in reader)
    if row_count == 0:
        return 0
    return max(row_count - 1, 0)


def fetch_huggingface_snapshot(
    source_spec: HuggingFaceSourceSpec,
    snapshot_spec: HuggingFaceSnapshotSpec,
    source_dir: Path,
    hf_token: str | None,
    fetch_timestamp: str,
) -> dict[str, Any]:
    output_path = source_dir / snapshot_spec.output_name

    logger.info(
        "Fetching Hugging Face dataset '%s' (config=%s, split=%s)",
        source_spec.dataset_id,
        snapshot_spec.config,
        snapshot_spec.split,
    )

    dataset = load_dataset(
        source_spec.dataset_id,
        snapshot_spec.config,
        split=snapshot_spec.split,
        trust_remote_code=False,
        token=hf_token,
        **snapshot_spec.load_dataset_kwargs,
    )
    record_count = write_jsonl(dataset, output_path)

    logger.info(
        "Snapshotted %s records for source '%s' into %s",
        record_count,
        source_spec.source_name,
        output_path,
    )

    return {
        "source_name": source_spec.source_name,
        "source_type": source_spec.source_type,
        "dataset_identifier": source_spec.dataset_id,
        "config": snapshot_spec.config,
        "split": snapshot_spec.split,
        "fetch_timestamp": fetch_timestamp,
        "snapshot_name": snapshot_spec.output_name,
        "output_file": output_path.name,
        "record_count": record_count,
        "byte_count": output_path.stat().st_size,
        "load_dataset_kwargs": snapshot_spec.load_dataset_kwargs,
    }


def fetch_github_raw_snapshot(
    source_spec: GitHubRawSourceSpec,
    snapshot_spec: GitHubRawSnapshotSpec,
    source_dir: Path,
    fetch_timestamp: str,
) -> dict[str, Any]:
    output_path = source_dir / snapshot_spec.output_name
    request = urllib.request.Request(
        snapshot_spec.url,
        headers={"User-Agent": "RedLib fetch_corpus.py"},
    )

    logger.info("Fetching GitHub raw file '%s'", snapshot_spec.url)
    try:
        with urllib.request.urlopen(request) as response:
            payload = response.read()
    except urllib.error.URLError as error:
        logger.error("Failed to fetch GitHub raw file '%s': %s", snapshot_spec.url, error)
        raise

    byte_count = write_raw_bytes(output_path, payload)
    record_count = count_csv_rows(payload) if snapshot_spec.format_label == "csv" else None

    logger.info(
        "Snapshotted raw file for source '%s' into %s (%s bytes)",
        source_spec.source_name,
        output_path,
        byte_count,
    )

    return {
        "source_name": source_spec.source_name,
        "source_type": source_spec.source_type,
        "repository": source_spec.repository,
        "url": snapshot_spec.url,
        "fetch_timestamp": fetch_timestamp,
        "snapshot_name": snapshot_spec.output_name,
        "output_file": output_path.name,
        "format_label": snapshot_spec.format_label,
        "record_count": record_count,
        "byte_count": byte_count,
    }


def fetch_snapshot(
    source_spec: SourceSpec,
    snapshot_spec: SnapshotSpec,
    source_dir: Path,
    hf_token: str | None,
    fetch_timestamp: str,
) -> dict[str, Any]:
    if source_spec.source_type == "huggingface":
        return fetch_huggingface_snapshot(
            source_spec=source_spec,
            snapshot_spec=snapshot_spec,
            source_dir=source_dir,
            hf_token=hf_token,
            fetch_timestamp=fetch_timestamp,
        )

    if source_spec.source_type == "github_raw":
        return fetch_github_raw_snapshot(
            source_spec=source_spec,
            snapshot_spec=snapshot_spec,
            source_dir=source_dir,
            fetch_timestamp=fetch_timestamp,
        )

    raise ValueError(f"Unsupported source_type: {source_spec.source_type}")


def write_source_metadata(source_dir: Path, metadata: dict[str, Any]) -> None:
    metadata_path = source_dir / "fetch_metadata.json"
    with metadata_path.open("w", encoding="utf-8", newline="\n") as metadata_file:
        json.dump(metadata, metadata_file, indent=2, ensure_ascii=False)
        metadata_file.write("\n")


def snapshot_source(
    source_spec: SourceSpec,
    raw_root: Path,
    hf_token: str | None,
    fetch_timestamp: str,
) -> dict[str, Any]:
    source_dir = raw_root / source_spec.source_name
    source_dir.mkdir(parents=True, exist_ok=True)

    snapshots_metadata = []
    total_records = 0
    total_bytes = 0
    has_countable_records = False

    for snapshot_spec in source_spec.snapshots:
        snapshot_metadata = fetch_snapshot(
            source_spec=source_spec,
            snapshot_spec=snapshot_spec,
            source_dir=source_dir,
            hf_token=hf_token,
            fetch_timestamp=fetch_timestamp,
        )
        snapshots_metadata.append(snapshot_metadata)
        total_bytes += snapshot_metadata["byte_count"]
        if snapshot_metadata["record_count"] is not None:
            has_countable_records = True
            total_records += snapshot_metadata["record_count"]

    source_metadata = {
        "source_name": source_spec.source_name,
        "source_type": source_spec.source_type,
        "fetch_timestamp": fetch_timestamp,
        "snapshot_count": len(source_spec.snapshots),
        "total_record_count": total_records if has_countable_records else None,
        "total_byte_count": total_bytes,
        "snapshots": snapshots_metadata,
    }
    if source_spec.source_type == "huggingface":
        source_metadata["dataset_identifier"] = source_spec.dataset_id
    if source_spec.source_type == "github_raw":
        source_metadata["repository"] = source_spec.repository

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


def fetch_all_sources() -> list[dict[str, Any]]:
    fetch_timestamp = datetime.now(timezone.utc).isoformat()
    hf_token = get_huggingface_token()
    staging_root = prepare_staging_root()

    source_summaries = []
    try:
        for source_spec in SOURCE_REGISTRY:
            source_summaries.append(
                snapshot_source(
                    source_spec=source_spec,
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
    summaries = fetch_all_sources()
    total_sources = len(summaries)
    total_bytes = sum(summary["total_byte_count"] for summary in summaries)
    countable_record_total = sum(
        summary["total_record_count"] or 0 for summary in summaries
    )
    logger.info(
        "Completed raw corpus snapshot for %s sources with %s countable records and %s total bytes",
        total_sources,
        countable_record_total,
        total_bytes,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
