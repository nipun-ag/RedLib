import csv
import json
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CORPUS_ROOT = Path("data") / "corpus"
RAW_ROOT = CORPUS_ROOT / "raw"
CANONICAL_ROOT = CORPUS_ROOT / "canonical"
CANONICAL_STAGING_ROOT = CORPUS_ROOT / "canonical_staging"

RAW_SOURCE_METADATA_FILENAME = "fetch_metadata.json"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def list_raw_source_files() -> list[Path]:
    source_files = []
    for source_dir in sorted(path for path in RAW_ROOT.iterdir() if path.is_dir()):
        for file_path in sorted(path for path in source_dir.iterdir() if path.is_file()):
            if file_path.name == RAW_SOURCE_METADATA_FILENAME:
                continue
            source_files.append(file_path)
    return source_files


def canonical_output_name(raw_file: Path) -> str:
    if raw_file.suffix.lower() == ".jsonl":
        return raw_file.name
    if raw_file.suffix.lower() == ".csv":
        return f"{raw_file.stem}.jsonl"
    raise SystemExit(
        f"Unsupported raw source format for {raw_file}. "
        "convert_sources.py currently supports only JSONL and CSV."
    )


def build_canonical_record(
    source_name: str,
    source_file: str,
    source_row: int,
    fields: Any,
) -> dict[str, Any]:
    if isinstance(fields, dict):
        canonical_fields = fields
    else:
        canonical_fields = {"_value": fields}

    return {
        "source": source_name,
        "source_file": source_file,
        "source_row": source_row,
        "fields": canonical_fields,
    }


def serialize_record(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def convert_jsonl_file(raw_file: Path, output_file: Any) -> int:
    record_count = 0
    with raw_file.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue

            try:
                parsed_record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Malformed JSONL in {raw_file} at line {line_number}: {error.msg}"
                ) from error

            canonical_record = build_canonical_record(
                source_name=raw_file.parent.name,
                source_file=raw_file.name,
                source_row=line_number,
                fields=parsed_record,
            )
            output_file.write(serialize_record(canonical_record))
            output_file.write("\n")
            record_count += 1

    return record_count


def convert_csv_file(raw_file: Path, output_file: Any) -> int:
    record_count = 0
    with raw_file.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            return 0

        for row in reader:
            canonical_record = build_canonical_record(
                source_name=raw_file.parent.name,
                source_file=raw_file.name,
                source_row=reader.line_num,
                fields=row,
            )
            output_file.write(serialize_record(canonical_record))
            output_file.write("\n")
            record_count += 1

    return record_count


def convert_source_file(raw_file: Path, canonical_root: Path) -> dict[str, Any]:
    source_name = raw_file.parent.name
    source_output_dir = canonical_root / source_name
    source_output_dir.mkdir(parents=True, exist_ok=True)

    output_name = canonical_output_name(raw_file)
    output_path = source_output_dir / output_name

    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        if raw_file.suffix.lower() == ".jsonl":
            record_count = convert_jsonl_file(raw_file, output_file)
        elif raw_file.suffix.lower() == ".csv":
            record_count = convert_csv_file(raw_file, output_file)
        else:
            raise SystemExit(
                f"Unsupported raw source format for {raw_file}. "
                "convert_sources.py currently supports only JSONL and CSV."
            )

    logger.info(
        "Converted %s into canonical %s with %s records",
        raw_file.relative_to(RAW_ROOT),
        output_path.relative_to(CANONICAL_STAGING_ROOT),
        record_count,
    )

    return {
        "source_name": source_name,
        "raw_file": raw_file.name,
        "canonical_file": output_name,
        "record_count": record_count,
    }


def prepare_canonical_staging_root() -> Path:
    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
    if CANONICAL_STAGING_ROOT.exists():
        shutil.rmtree(CANONICAL_STAGING_ROOT)
    CANONICAL_STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    return CANONICAL_STAGING_ROOT


def replace_canonical_snapshot(staging_root: Path) -> None:
    if CANONICAL_ROOT.exists():
        shutil.rmtree(CANONICAL_ROOT)
    staging_root.replace(CANONICAL_ROOT)


def convert_all_sources() -> dict[str, Any]:
    if not RAW_ROOT.exists():
        raise SystemExit(
            "Raw corpus directory not found at data/corpus/raw/. "
            "Run fetch_corpus.py before convert_sources.py."
        )

    raw_source_files = list_raw_source_files()
    staging_root = prepare_canonical_staging_root()

    file_summaries = []
    try:
        for raw_file in raw_source_files:
            file_summaries.append(convert_source_file(raw_file, staging_root))
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise

    replace_canonical_snapshot(staging_root)

    return {
        "source_file_count": len(raw_source_files),
        "canonical_record_count": sum(
            summary["record_count"] for summary in file_summaries
        ),
        "file_summaries": file_summaries,
    }


def main() -> int:
    configure_logging()
    result = convert_all_sources()
    logger.info(
        "Converted %s source files into %s canonical records under %s",
        result["source_file_count"],
        result["canonical_record_count"],
        CANONICAL_ROOT,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
