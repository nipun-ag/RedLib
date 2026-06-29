import hashlib
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CORPUS_ROOT = Path("data") / "corpus"
CANONICAL_ROOT = CORPUS_ROOT / "canonical"
AUDIT_REPORT_PATH = CORPUS_ROOT / "audit_report.json"

SHORT_TEXT_THRESHOLD = 20
LONG_TEXT_THRESHOLD = 2000
MAX_DUPLICATE_SAMPLES = 10
MAX_MALFORMED_LINE_SAMPLES = 10
MAX_SCHEMA_VARIANTS = 10
MAX_TEXT_SAMPLE_LENGTH = 160

HTML_ENTITY_PATTERN = re.compile(
    r"&(?:[A-Za-z][A-Za-z0-9]{1,31}|#[0-9]{1,8}|#x[0-9A-Fa-f]{1,8});"
)
ESCAPED_NEWLINE_PATTERN = re.compile(r"\\r\\n|\\n|\\r")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def truncate_text(text: str, limit: int = MAX_TEXT_SAMPLE_LENGTH) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def count_suspicious_control_characters(text: str) -> int:
    suspicious_count = 0
    for character in text:
        codepoint = ord(character)
        if codepoint == 127 or (codepoint < 32 and character not in "\n\r\t"):
            suspicious_count += 1
    return suspicious_count


def is_effectively_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def is_empty_record(record: Any) -> bool:
    if isinstance(record, dict):
        if not record:
            return True
        return all(is_effectively_empty(value) for value in record.values())
    return is_effectively_empty(record)


def schema_variant_label(record: Any) -> tuple[str, ...]:
    if isinstance(record, dict):
        return tuple(sorted(record.keys()))
    return (f"<NON_OBJECT:{type(record).__name__}>",)


def source_name_for_file(file_path: Path) -> str:
    relative_path = file_path.relative_to(CANONICAL_ROOT)
    return relative_path.parts[0]


def relative_posix_path(file_path: Path) -> str:
    return file_path.relative_to(CANONICAL_ROOT).as_posix()


def provenance_label(canonical_record: dict[str, Any], file_path: Path, line_number: int) -> str:
    source_name = canonical_record.get("source")
    source_file = canonical_record.get("source_file")
    source_row = canonical_record.get("source_row")
    if source_name and source_file and isinstance(source_row, int):
        return f"{source_name}/{source_file}:{source_row}"
    return f"{relative_posix_path(file_path)}:{line_number}"


@dataclass
class FieldStats:
    present_count: int = 0
    null_count: int = 0
    non_string_count: int = 0
    string_count: int = 0
    non_empty_string_count: int = 0
    total_string_length: int = 0
    min_string_length: int | None = None
    max_string_length: int | None = None
    short_text_count: int = 0
    long_text_count: int = 0
    html_entity_count: int = 0
    escaped_newline_count: int = 0
    suspicious_control_character_count: int = 0
    suspicious_control_character_instances: int = 0
    value_type_counts: Counter[str] = field(default_factory=Counter)

    def update(self, value: Any) -> None:
        self.present_count += 1
        self.value_type_counts[type(value).__name__] += 1

        if value is None:
            self.null_count += 1
            return

        if not isinstance(value, str):
            self.non_string_count += 1
            return

        self.string_count += 1
        text_length = len(value)
        self.total_string_length += text_length
        self.min_string_length = (
            text_length
            if self.min_string_length is None
            else min(self.min_string_length, text_length)
        )
        self.max_string_length = (
            text_length
            if self.max_string_length is None
            else max(self.max_string_length, text_length)
        )

        stripped_value = value.strip()
        if stripped_value:
            self.non_empty_string_count += 1
            if len(stripped_value) <= SHORT_TEXT_THRESHOLD:
                self.short_text_count += 1
        if text_length >= LONG_TEXT_THRESHOLD:
            self.long_text_count += 1
        if HTML_ENTITY_PATTERN.search(value):
            self.html_entity_count += 1
        if ESCAPED_NEWLINE_PATTERN.search(value):
            self.escaped_newline_count += 1

        suspicious_control_count = count_suspicious_control_characters(value)
        if suspicious_control_count:
            self.suspicious_control_character_count += 1
            self.suspicious_control_character_instances += suspicious_control_count

    def to_report(self, total_records: int) -> dict[str, Any]:
        missing_count = max(total_records - self.present_count, 0)
        average_string_length = (
            self.total_string_length / self.string_count if self.string_count else 0.0
        )
        non_empty_string_ratio = (
            self.non_empty_string_count / total_records if total_records else 0.0
        )
        return {
            "present_count": self.present_count,
            "missing_count": missing_count,
            "null_count": self.null_count,
            "string_count": self.string_count,
            "non_string_count": self.non_string_count,
            "non_empty_string_count": self.non_empty_string_count,
            "non_empty_string_ratio": round(non_empty_string_ratio, 4),
            "average_string_length": round(average_string_length, 2),
            "min_string_length": self.min_string_length,
            "max_string_length": self.max_string_length,
            "short_text_count": self.short_text_count,
            "long_text_count": self.long_text_count,
            "html_entity_count": self.html_entity_count,
            "escaped_newline_count": self.escaped_newline_count,
            "suspicious_control_character_count": (
                self.suspicious_control_character_count
            ),
            "suspicious_control_character_instances": (
                self.suspicious_control_character_instances
            ),
            "value_type_counts": dict(sorted(self.value_type_counts.items())),
        }


@dataclass
class DuplicateSample:
    count: int = 0
    sample_text: str | None = None
    first_seen_at: str | None = None


@dataclass
class ScopeAggregator:
    total_records: int = 0
    empty_records: int = 0
    non_object_records: int = 0
    malformed_jsonl_lines: int = 0
    malformed_line_samples: list[dict[str, Any]] = field(default_factory=list)
    field_stats: dict[str, FieldStats] = field(default_factory=dict)
    schema_variants: Counter[tuple[str, ...]] = field(default_factory=Counter)
    raw_record_duplicates: dict[str, DuplicateSample] = field(default_factory=dict)
    text_duplicates_by_field: dict[str, dict[str, DuplicateSample]] = field(
        default_factory=dict
    )

    def observe_malformed_line(
        self,
        file_path: Path,
        line_number: int,
        line_text: str,
        error_message: str,
    ) -> None:
        self.malformed_jsonl_lines += 1
        if len(self.malformed_line_samples) >= MAX_MALFORMED_LINE_SAMPLES:
            return
        self.malformed_line_samples.append(
            {
                "file": relative_posix_path(file_path),
                "line_number": line_number,
                "error": error_message,
                "line_excerpt": truncate_text(line_text.strip(), 120),
            }
        )

    def observe_record(self, record_fields: Any, location: str) -> None:
        self.total_records += 1

        if is_empty_record(record_fields):
            self.empty_records += 1
        if not isinstance(record_fields, dict):
            self.non_object_records += 1

        self.schema_variants[schema_variant_label(record_fields)] += 1

        canonical_record = canonical_json(record_fields)
        record_hash = stable_hash(canonical_record)
        duplicate_sample = self.raw_record_duplicates.setdefault(
            record_hash,
            DuplicateSample(
                count=0,
                sample_text=truncate_text(canonical_record),
                first_seen_at=location,
            ),
        )
        duplicate_sample.count += 1

        if not isinstance(record_fields, dict):
            return

        for field_name, value in record_fields.items():
            stats = self.field_stats.setdefault(field_name, FieldStats())
            stats.update(value)

            if not isinstance(value, str):
                continue

            if not value.strip():
                continue

            field_duplicates = self.text_duplicates_by_field.setdefault(field_name, {})
            text_hash = stable_hash(value)
            text_sample = field_duplicates.setdefault(
                text_hash,
                DuplicateSample(
                    count=0,
                    sample_text=truncate_text(value),
                    first_seen_at=location,
                ),
            )
            text_sample.count += 1

    def infer_likely_prompt_fields(self) -> list[dict[str, Any]]:
        candidates = []
        for field_name, stats in self.field_stats.items():
            if self.total_records == 0 or stats.non_empty_string_count == 0:
                continue

            coverage_ratio = stats.non_empty_string_count / self.total_records
            average_length = (
                stats.total_string_length / stats.string_count if stats.string_count else 0
            )
            candidate_score = (coverage_ratio * 0.65) + (
                min(average_length / 500, 1.0) * 0.35
            )

            if coverage_ratio < 0.05 or average_length < SHORT_TEXT_THRESHOLD:
                continue

            candidates.append(
                {
                    "field_name": field_name,
                    "coverage_ratio": round(coverage_ratio, 4),
                    "non_empty_string_count": stats.non_empty_string_count,
                    "average_string_length": round(average_length, 2),
                    "candidate_score": round(candidate_score, 4),
                }
            )

        candidates.sort(
            key=lambda item: (
                item["candidate_score"],
                item["average_string_length"],
                item["non_empty_string_count"],
                item["field_name"],
            ),
            reverse=True,
        )
        return candidates

    def summarize_duplicate_samples(
        self,
        samples: dict[str, DuplicateSample],
    ) -> dict[str, Any]:
        duplicate_occurrences = 0
        duplicate_groups = 0
        duplicate_examples = []

        for sample in samples.values():
            if sample.count < 2:
                continue
            duplicate_groups += 1
            duplicate_occurrences += sample.count - 1
            if len(duplicate_examples) < MAX_DUPLICATE_SAMPLES:
                duplicate_examples.append(
                    {
                        "count": sample.count,
                        "first_seen_at": sample.first_seen_at,
                        "sample": sample.sample_text,
                    }
                )

        duplicate_examples.sort(
            key=lambda item: (item["count"], item["first_seen_at"] or ""),
            reverse=True,
        )
        return {
            "duplicate_groups": duplicate_groups,
            "duplicate_occurrences": duplicate_occurrences,
            "samples": duplicate_examples,
        }

    def summarize_likely_prompt_duplicates(
        self,
        likely_fields: list[dict[str, Any]],
    ) -> dict[str, Any]:
        by_field = {}
        total_duplicate_groups = 0
        total_duplicate_occurrences = 0

        for candidate in likely_fields:
            field_name = candidate["field_name"]
            field_summary = self.summarize_duplicate_samples(
                self.text_duplicates_by_field.get(field_name, {})
            )
            if (
                field_summary["duplicate_groups"] == 0
                and field_summary["duplicate_occurrences"] == 0
            ):
                continue

            total_duplicate_groups += field_summary["duplicate_groups"]
            total_duplicate_occurrences += field_summary["duplicate_occurrences"]
            by_field[field_name] = field_summary

        return {
            "duplicate_groups": total_duplicate_groups,
            "duplicate_occurrences": total_duplicate_occurrences,
            "by_field": by_field,
        }

    def summarize_schema_variants(self) -> dict[str, Any]:
        variants = [
            {"fields": list(fields), "count": count}
            for fields, count in self.schema_variants.most_common(MAX_SCHEMA_VARIANTS)
        ]
        dominant_fields = variants[0]["fields"] if variants else []
        dominant_count = variants[0]["count"] if variants else 0
        return {
            "variant_count": len(self.schema_variants),
            "dominant_fields": dominant_fields,
            "dominant_count": dominant_count,
            "variants": variants,
        }

    def to_report(self) -> dict[str, Any]:
        likely_fields = self.infer_likely_prompt_fields()
        fields_report = {
            field_name: stats.to_report(self.total_records)
            for field_name, stats in sorted(self.field_stats.items())
        }

        return {
            "total_records": self.total_records,
            "empty_records": self.empty_records,
            "non_object_records": self.non_object_records,
            "malformed_jsonl_lines": self.malformed_jsonl_lines,
            "malformed_line_samples": self.malformed_line_samples,
            "likely_prompt_bearing_fields": likely_fields,
            "duplicate_raw_records": self.summarize_duplicate_samples(
                self.raw_record_duplicates
            ),
            "duplicate_likely_prompt_text": self.summarize_likely_prompt_duplicates(
                likely_fields
            ),
            "schema_variation": self.summarize_schema_variants(),
            "fields": fields_report,
        }


def list_canonical_jsonl_files() -> list[Path]:
    return sorted(CANONICAL_ROOT.glob("*/*.jsonl"))


def audit_canonical_jsonl_file(
    file_path: Path,
    corpus_scope: ScopeAggregator,
    source_scope: ScopeAggregator,
    file_scope: ScopeAggregator,
) -> None:
    with file_path.open("r", encoding="utf-8") as source_file:
        for line_number, line in enumerate(source_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                error_message = "Blank line"
                corpus_scope.observe_malformed_line(file_path, line_number, line, error_message)
                source_scope.observe_malformed_line(file_path, line_number, line, error_message)
                file_scope.observe_malformed_line(file_path, line_number, line, error_message)
                continue

            try:
                canonical_record = json.loads(line)
            except json.JSONDecodeError as error:
                corpus_scope.observe_malformed_line(file_path, line_number, line, error.msg)
                source_scope.observe_malformed_line(file_path, line_number, line, error.msg)
                file_scope.observe_malformed_line(file_path, line_number, line, error.msg)
                continue

            if not isinstance(canonical_record, dict):
                error_message = "Canonical record is not a JSON object"
                corpus_scope.observe_malformed_line(file_path, line_number, line, error_message)
                source_scope.observe_malformed_line(file_path, line_number, line, error_message)
                file_scope.observe_malformed_line(file_path, line_number, line, error_message)
                continue

            record_fields = canonical_record.get("fields")
            if not isinstance(record_fields, dict):
                error_message = "Canonical record fields payload is not a JSON object"
                corpus_scope.observe_malformed_line(file_path, line_number, line, error_message)
                source_scope.observe_malformed_line(file_path, line_number, line, error_message)
                file_scope.observe_malformed_line(file_path, line_number, line, error_message)
                continue

            location = provenance_label(canonical_record, file_path, line_number)
            corpus_scope.observe_record(record_fields, location)
            source_scope.observe_record(record_fields, location)
            file_scope.observe_record(record_fields, location)


def audit_canonical_corpus() -> dict[str, Any]:
    if not CANONICAL_ROOT.exists():
        raise SystemExit(
            "Canonical corpus directory not found at data/corpus/canonical/. "
            "Run convert_sources.py before audit_corpus.py."
        )

    corpus_scope = ScopeAggregator()
    source_scopes: dict[str, ScopeAggregator] = {}
    file_scopes: dict[str, ScopeAggregator] = {}

    jsonl_files = list_canonical_jsonl_files()
    logger.info("Auditing %s canonical JSONL files from %s", len(jsonl_files), CANONICAL_ROOT)

    for file_path in jsonl_files:
        source_name = source_name_for_file(file_path)
        source_scope = source_scopes.setdefault(source_name, ScopeAggregator())
        file_key = relative_posix_path(file_path)
        file_scope = file_scopes.setdefault(file_key, ScopeAggregator())

        audit_canonical_jsonl_file(
            file_path=file_path,
            corpus_scope=corpus_scope,
            source_scope=source_scope,
            file_scope=file_scope,
        )

    source_file_counts = Counter()
    for file_name in file_scopes:
        source_file_counts[file_name.split("/", 1)[0]] += 1

    sources_report = {}
    per_source_record_counts = {}
    for source_name, scope in sorted(source_scopes.items()):
        source_report = scope.to_report()
        source_report["file_count"] = source_file_counts[source_name]
        sources_report[source_name] = source_report
        per_source_record_counts[source_name] = source_report["total_records"]

    files_report = {}
    for file_name, scope in sorted(file_scopes.items()):
        file_report = scope.to_report()
        file_report["source_name"] = file_name.split("/", 1)[0]
        files_report[file_name] = file_report

    corpus_report = corpus_scope.to_report()
    corpus_report["total_sources"] = len(source_scopes)
    corpus_report["total_files"] = len(jsonl_files)
    corpus_report["per_source_record_counts"] = per_source_record_counts

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canonical_root": str(CANONICAL_ROOT),
        "report_path": str(AUDIT_REPORT_PATH),
        "report_version": 2,
        "analysis_constraints": {
            "raw_data_modified": False,
            "canonical_data_modified": False,
            "normalized_artifacts_created": False,
            "notes": [
                "This report consumes canonical converted source records, not platform-native raw file formats.",
                "Likely prompt-bearing fields are inferred statistically from preserved source fields only and do not choose a canonical prompt field.",
                "Duplicate likely prompt text is limited to inferred candidate fields and may miss semantically equivalent prompts across different field names.",
            ],
        },
        "thresholds": {
            "short_text_threshold": SHORT_TEXT_THRESHOLD,
            "long_text_threshold": LONG_TEXT_THRESHOLD,
            "max_duplicate_samples": MAX_DUPLICATE_SAMPLES,
            "max_malformed_line_samples": MAX_MALFORMED_LINE_SAMPLES,
            "max_schema_variants": MAX_SCHEMA_VARIANTS,
        },
        "corpus_summary": corpus_report,
        "source_summaries": sources_report,
        "file_summaries": files_report,
    }


def write_audit_report(report: dict[str, Any]) -> None:
    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
    with AUDIT_REPORT_PATH.open("w", encoding="utf-8", newline="\n") as report_file:
        json.dump(report, report_file, indent=2, ensure_ascii=False)
        report_file.write("\n")


def main() -> int:
    configure_logging()
    report = audit_canonical_corpus()
    write_audit_report(report)
    logger.info(
        "Wrote corpus audit report for %s sources, %s files, and %s records to %s",
        report["corpus_summary"]["total_sources"],
        report["corpus_summary"]["total_files"],
        report["corpus_summary"]["total_records"],
        AUDIT_REPORT_PATH,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
