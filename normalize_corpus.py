import hashlib
import html
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CORPUS_ROOT = Path("data") / "corpus"
CANONICAL_ROOT = CORPUS_ROOT / "canonical"
AUDIT_REPORT_PATH = CORPUS_ROOT / "audit_report.json"
NORMALIZED_PATH = CORPUS_ROOT / "normalized.jsonl"
NORMALIZED_STAGING_PATH = CORPUS_ROOT / "normalized_staging.jsonl"

PROMPT_FIELD_MAPPINGS: dict[str, dict[str, str]] = {
    "trustairlab": {
        "jailbreak_2023_05_07_train.jsonl": "prompt",
        "jailbreak_2023_12_25_train.jsonl": "prompt",
    },
    "rubend18": {
        "train.jsonl": "Prompt",
    },
    "jackhhao": {
        "train.jsonl": "prompt",
        "test.jsonl": "prompt",
    },
    "harmbench": {
        "HumanJailbreaks_val.jsonl": "Behavior",
        "HumanJailbreaks_test.jsonl": "Behavior",
    },
    "advbench": {
        "harmful_behaviors.csv": "goal",
    },
    "jailbreakbench_behaviors": {
        "behaviors_harmful.jsonl": "Goal",
    },
    "maliciousinstruct": {
        "train.jsonl": "prompt",
    },
    "wildjailbreak": {
        "train.jsonl": "adversarial",
        "eval.jsonl": "adversarial",
    },
}

INVALID_CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
TRAILING_HORIZONTAL_WHITESPACE_PATTERN = re.compile(r"[ \t\f\v]+(?=\n|$)")
REPEATED_BLANK_LINES_PATTERN = re.compile(r"\n{3,}")
MULTI_SPACE_BETWEEN_NONSPACE_PATTERN = re.compile(r"(?<=\S)[ \t\f\v]{2,}(?=\S)")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def relative_posix_path(file_path: Path) -> str:
    return file_path.relative_to(CANONICAL_ROOT).as_posix()


def list_canonical_jsonl_files() -> list[Path]:
    return sorted(CANONICAL_ROOT.glob("*/*.jsonl"))


def load_optional_audit_report() -> dict[str, Any] | None:
    if not AUDIT_REPORT_PATH.exists():
        logger.info(
            "No audit report found at %s; continuing without it",
            AUDIT_REPORT_PATH,
        )
        return None

    with AUDIT_REPORT_PATH.open("r", encoding="utf-8") as audit_file:
        audit_report = json.load(audit_file)
    logger.info("Loaded audit report from %s", AUDIT_REPORT_PATH)
    return audit_report


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def get_prompt_field(source_name: str, source_file: str) -> str:
    source_mapping = PROMPT_FIELD_MAPPINGS.get(source_name)
    if source_mapping is None:
        raise SystemExit(
            f"No prompt-field mapping configured for source '{source_name}'. "
            "Normalization requires explicit mappings."
        )

    prompt_field = source_mapping.get(source_file)
    if prompt_field is None:
        raise SystemExit(
            f"No prompt-field mapping configured for source '{source_name}' "
            f"file '{source_file}'. Normalization requires explicit mappings."
        )

    return prompt_field


def validate_mapping_against_audit(
    audit_report: dict[str, Any] | None,
    canonical_file_key: str,
    prompt_field: str,
) -> None:
    if audit_report is None:
        return

    file_summary = audit_report.get("file_summaries", {}).get(canonical_file_key)
    if not file_summary:
        logger.warning(
            "Audit report does not contain a file summary for canonical file %s",
            canonical_file_key,
        )
        return

    file_fields = file_summary.get("fields", {})
    if prompt_field not in file_fields:
        logger.warning(
            "Mapped prompt field '%s' was not present in audit field stats for %s",
            prompt_field,
            canonical_file_key,
        )

    likely_fields = {
        candidate.get("field_name")
        for candidate in file_summary.get("likely_prompt_bearing_fields", [])
    }
    if likely_fields and prompt_field not in likely_fields:
        logger.warning(
            "Mapped prompt field '%s' is not among audit-derived likely prompt fields for %s: %s",
            prompt_field,
            canonical_file_key,
            sorted(likely_fields),
        )


def normalize_prompt_text(text: str) -> str:
    normalized_text = html.unescape(text)
    normalized_text = normalized_text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_text = normalized_text.replace("\u00A0", " ")
    normalized_text = INVALID_CONTROL_CHARACTER_PATTERN.sub("", normalized_text)
    normalized_text = TRAILING_HORIZONTAL_WHITESPACE_PATTERN.sub("", normalized_text)
    normalized_text = MULTI_SPACE_BETWEEN_NONSPACE_PATTERN.sub(" ", normalized_text)
    normalized_text = REPEATED_BLANK_LINES_PATTERN.sub("\n\n", normalized_text)
    normalized_text = normalized_text.strip()
    return normalized_text


def build_prompt_id(
    source_name: str,
    source_file: str,
    source_row: int,
    raw_fields: dict[str, Any],
) -> str:
    prompt_id_material = canonical_json(
        {
            "source": source_name,
            "source_file": source_file,
            "source_row": source_row,
            "raw_fields": raw_fields,
        }
    )
    prompt_hash = hashlib.sha256(prompt_id_material.encode("utf-8")).hexdigest()[:20]
    return f"{source_name}_{prompt_hash}"


def serialize_record(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def normalize_record(
    canonical_record: dict[str, Any],
    raw_fields: dict[str, Any],
    prompt_field: str,
) -> dict[str, Any] | None:
    raw_text = raw_fields.get(prompt_field)
    if not isinstance(raw_text, str):
        return None

    normalized_text = normalize_prompt_text(raw_text)
    if not normalized_text:
        return None

    source_name = canonical_record["source"]
    source_file = canonical_record["source_file"]
    source_row = canonical_record["source_row"]

    return {
        "prompt_id": build_prompt_id(
            source_name=source_name,
            source_file=source_file,
            source_row=source_row,
            raw_fields=raw_fields,
        ),
        "source": source_name,
        "source_file": source_file,
        "source_row": source_row,
        "text": normalized_text,
        "raw_fields": raw_fields,
    }


def normalize_file(
    file_path: Path,
    output_file: Any,
    audit_report: dict[str, Any] | None,
) -> dict[str, int]:
    canonical_file_key = relative_posix_path(file_path)
    counts = {
        "read_lines": 0,
        "normalized_records": 0,
        "skipped_blank_lines": 0,
        "skipped_malformed_lines": 0,
        "skipped_invalid_canonical_records": 0,
        "skipped_missing_or_non_string_prompt_field": 0,
        "skipped_empty_normalized_text": 0,
    }
    validated_fields: set[str] = set()

    with file_path.open("r", encoding="utf-8") as canonical_file:
        for line_number, line in enumerate(canonical_file, start=1):
            counts["read_lines"] += 1
            stripped_line = line.strip()

            if not stripped_line:
                counts["skipped_blank_lines"] += 1
                continue

            try:
                canonical_record = json.loads(line)
            except json.JSONDecodeError:
                counts["skipped_malformed_lines"] += 1
                continue

            if not isinstance(canonical_record, dict):
                counts["skipped_invalid_canonical_records"] += 1
                continue

            source_name = canonical_record.get("source")
            source_file = canonical_record.get("source_file")
            source_row = canonical_record.get("source_row")
            raw_fields = canonical_record.get("fields")

            if (
                not isinstance(source_name, str)
                or not isinstance(source_file, str)
                or not isinstance(source_row, int)
                or not isinstance(raw_fields, dict)
            ):
                counts["skipped_invalid_canonical_records"] += 1
                continue

            prompt_field = get_prompt_field(source_name, source_file)
            if prompt_field not in validated_fields:
                validate_mapping_against_audit(
                    audit_report=audit_report,
                    canonical_file_key=canonical_file_key,
                    prompt_field=prompt_field,
                )
                validated_fields.add(prompt_field)

            raw_text = raw_fields.get(prompt_field)
            if not isinstance(raw_text, str):
                counts["skipped_missing_or_non_string_prompt_field"] += 1
                continue

            normalized_record = normalize_record(
                canonical_record=canonical_record,
                raw_fields=raw_fields,
                prompt_field=prompt_field,
            )
            if normalized_record is None:
                counts["skipped_empty_normalized_text"] += 1
                continue

            output_file.write(serialize_record(normalized_record))
            output_file.write("\n")
            counts["normalized_records"] += 1

    logger.info(
        "Normalized canonical file %s: %s records written, %s lines skipped",
        canonical_file_key,
        counts["normalized_records"],
        (
            counts["skipped_blank_lines"]
            + counts["skipped_malformed_lines"]
            + counts["skipped_invalid_canonical_records"]
            + counts["skipped_missing_or_non_string_prompt_field"]
            + counts["skipped_empty_normalized_text"]
        ),
    )
    return counts


def normalize_corpus() -> dict[str, Any]:
    if not CANONICAL_ROOT.exists():
        raise SystemExit(
            "Canonical corpus directory not found at data/corpus/canonical/. "
            "Run convert_sources.py before normalize_corpus.py."
        )

    audit_report = load_optional_audit_report()
    jsonl_files = list_canonical_jsonl_files()
    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)

    totals = {
        "files": len(jsonl_files),
        "read_lines": 0,
        "normalized_records": 0,
        "skipped_blank_lines": 0,
        "skipped_malformed_lines": 0,
        "skipped_invalid_canonical_records": 0,
        "skipped_missing_or_non_string_prompt_field": 0,
        "skipped_empty_normalized_text": 0,
    }
    per_file_counts: dict[str, dict[str, int]] = {}

    with NORMALIZED_STAGING_PATH.open("w", encoding="utf-8", newline="\n") as output_file:
        for file_path in jsonl_files:
            file_counts = normalize_file(
                file_path=file_path,
                output_file=output_file,
                audit_report=audit_report,
            )
            per_file_counts[relative_posix_path(file_path)] = file_counts
            for key in totals:
                if key == "files":
                    continue
                totals[key] += file_counts[key]

    NORMALIZED_STAGING_PATH.replace(NORMALIZED_PATH)

    return {
        "normalized_path": str(NORMALIZED_PATH),
        "totals": totals,
        "per_file_counts": per_file_counts,
    }


def main() -> int:
    configure_logging()
    result = normalize_corpus()
    totals = result["totals"]
    logger.info(
        "Wrote %s normalized records from %s canonical files to %s",
        totals["normalized_records"],
        totals["files"],
        result["normalized_path"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
