import argparse
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

CORPUS_ROOT = Path("data") / "corpus"
NORMALIZED_PATH = CORPUS_ROOT / "normalized.jsonl"
PROPOSED_TAXONOMY_PATH = CORPUS_ROOT / "proposed_taxonomy.json"
CLASSIFIED_PATH = CORPUS_ROOT / "classified.jsonl"
CLASSIFIED_STAGING_PATH = CORPUS_ROOT / "classified_staging.jsonl"
CLASSIFICATION_CHECKPOINT_PATH = CORPUS_ROOT / "classified_checkpoint.json"
CLASSIFICATION_FAILURE_LOG_PATH = CORPUS_ROOT / "classification_failures.jsonl"
CLASSIFICATION_DEBUG_DIR = CORPUS_ROOT / "classification_debug"

MODEL_NAME = os.environ.get("REDLIB_CLASSIFY_MODEL", "claude-haiku-4-5")
BATCH_SIZE = int(os.environ.get("REDLIB_CLASSIFY_BATCH_SIZE", "24"))
MAX_OUTPUT_TOKENS = int(os.environ.get("REDLIB_CLASSIFY_MAX_OUTPUT_TOKENS", "3500"))
MAX_PROMPT_CHARS = int(os.environ.get("REDLIB_CLASSIFY_MAX_PROMPT_CHARS", "1600"))
MAX_BATCH_INPUT_TOKENS = int(
    os.environ.get("REDLIB_CLASSIFY_MAX_INPUT_TOKENS", "32000")
)
MAX_RETRIES_PER_BATCH = int(os.environ.get("REDLIB_CLASSIFY_MAX_RETRIES", "3"))
RETRY_BASE_DELAY_SECONDS = float(
    os.environ.get("REDLIB_CLASSIFY_RETRY_BASE_DELAY_SECONDS", "2.0")
)
CHECKPOINT_EVERY_BATCHES = int(
    os.environ.get("REDLIB_CLASSIFY_CHECKPOINT_EVERY_BATCHES", "1")
)
INPUT_COST_PER_MILLION_USD = float(
    os.environ.get("REDLIB_CLASSIFY_INPUT_COST_PER_MILLION_USD", "0")
)
OUTPUT_COST_PER_MILLION_USD = float(
    os.environ.get("REDLIB_CLASSIFY_OUTPUT_COST_PER_MILLION_USD", "0")
)

PRIMARY_FALLBACK_CATEGORY = "Unclear / Needs Review"
FALLBACK_RATIONALE = (
    "Automatic classification could not validate a taxonomy-safe dominant "
    "mechanism for this prompt."
)
SUPPORTING_TRAIT_OPTIONS = [
    "Research Pretext",
    "Professional Context",
    "Creative Writing Framing",
    "Persona Support",
    "Fictional Framing Support",
    "Simulation / Sandbox Support",
    "Authority Claim Support",
    "Benign Justification",
    "Educational Framing",
    "Roleplay Support",
]

SYSTEM_PROMPT = """You classify jailbreak prompts against an approved operational taxonomy.

Your job is to assign one dominant primary jailbreak mechanism per prompt.

Hard rules:
- Return structured output only.
- Choose exactly one primary category from the provided list, or the explicit fallback category when no approved category fits.
- Do not invent new primary categories, subtechniques, or supporting traits.
- Primary category means the mechanism that most directly contributes to bypassing model safety behavior.
- Supporting traits are secondary signals only. Do not promote a secondary trait into the primary category unless it is the main bypass mechanism.
- If multiple mechanisms appear, choose the single dominant one and use supporting traits for the rest.
- Keep rationale short, concrete, and mechanism-focused.
- Do not reproduce or quote long prompt text.
"""


class PromptClassificationOutput(BaseModel):
    prompt_id: str = Field(min_length=1)
    primary_category: str = Field(min_length=1)
    subtechnique: str | None = None
    supporting_traits: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=240)


class BatchClassificationOutput(BaseModel):
    classifications: list[PromptClassificationOutput] = Field(default_factory=list)


@dataclass(frozen=True)
class NormalizedRecord:
    prompt_id: str
    source: str
    source_file: str
    source_row: int
    text: str
    raw_fields: dict[str, Any]


@dataclass(frozen=True)
class TaxonomyCategory:
    name: str
    description: str
    distinguishing_traits: list[str]
    subtechniques: dict[str, str]


@dataclass(frozen=True)
class ClassificationResult:
    primary_category: str
    subtechnique: str | None
    supporting_traits: list[str]
    confidence: float
    rationale: str


@dataclass(frozen=True)
class BatchRequestResult:
    classifications: dict[str, ClassificationResult]
    estimated_input_tokens: int | None
    actual_input_tokens: int
    actual_output_tokens: int
    stop_reason: str | None
    attempt_count: int


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def canonical_label(value: str) -> str:
    return " ".join(value.strip().lower().split())


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_file_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_int(value: Any, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float | None:
    if INPUT_COST_PER_MILLION_USD <= 0 and OUTPUT_COST_PER_MILLION_USD <= 0:
        return None
    return round(
        (input_tokens / 1_000_000 * INPUT_COST_PER_MILLION_USD)
        + (output_tokens / 1_000_000 * OUTPUT_COST_PER_MILLION_USD),
        6,
    )


def get_anthropic_client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Run with Doppler or export the key before classify_corpus.py."
        )
    return Anthropic(api_key=api_key)


def extract_text_content(response: Any) -> str:
    text_parts = []
    for block in getattr(response, "content", []):
        block_text = getattr(block, "text", None)
        if block_text:
            text_parts.append(block_text)
    return "\n".join(text_parts).strip()


def write_debug_payload(
    *,
    batch_prompt_ids: list[str],
    response_stage: str,
    error_message: str,
    response: Any | None = None,
    estimated_input_tokens: int | None = None,
    extra_context: dict[str, Any] | None = None,
) -> Path:
    CLASSIFICATION_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prompt_stub = batch_prompt_ids[0] if batch_prompt_ids else "batch"
    debug_path = (
        CLASSIFICATION_DEBUG_DIR
        / f"{prompt_stub}_{response_stage}_{timestamp}.json"
    )
    payload = {
        "generated_at": now_utc_iso(),
        "model": MODEL_NAME,
        "batch_prompt_ids": batch_prompt_ids,
        "response_stage": response_stage,
        "error": error_message,
        "estimated_input_tokens": estimated_input_tokens,
        "stop_reason": getattr(response, "stop_reason", None) if response else None,
        "usage": (
            {
                "input_tokens": getattr(response.usage, "input_tokens", None),
                "output_tokens": getattr(response.usage, "output_tokens", None),
            }
            if response and getattr(response, "usage", None)
            else None
        ),
        "raw_response": extract_text_content(response) if response else "",
        "extra_context": extra_context or {},
    }
    with debug_path.open("w", encoding="utf-8", newline="\n") as debug_file:
        json.dump(payload, debug_file, indent=2, ensure_ascii=False)
        debug_file.write("\n")
    return debug_path


def log_failure_event(event: dict[str, Any]) -> None:
    with CLASSIFICATION_FAILURE_LOG_PATH.open("a", encoding="utf-8", newline="\n") as log:
        json.dump(event, log, ensure_ascii=False)
        log.write("\n")


def load_taxonomy() -> tuple[dict[str, TaxonomyCategory], str]:
    if not PROPOSED_TAXONOMY_PATH.exists():
        raise SystemExit(
            "Proposed taxonomy not found at data/corpus/proposed_taxonomy.json. "
            "Run discover_taxonomy.py before classify_corpus.py."
        )

    with PROPOSED_TAXONOMY_PATH.open("r", encoding="utf-8") as taxonomy_file:
        payload = json.load(taxonomy_file)

    if payload.get("human_review_required") is True:
        logger.warning(
            "proposed_taxonomy.json still marks human_review_required=true. "
            "Classification will proceed because this stage was explicitly requested, "
            "but the taxonomy should normally be human-approved before full-corpus application."
        )

    raw_categories = payload.get("top_level_categories")
    if not isinstance(raw_categories, list) or not raw_categories:
        raise SystemExit(
            "Proposed taxonomy does not contain any top_level_categories to classify against."
        )

    taxonomy: dict[str, TaxonomyCategory] = {}
    for category_payload in raw_categories:
        if not isinstance(category_payload, dict):
            raise SystemExit("Proposed taxonomy contains a non-object category entry.")

        name = category_payload.get("name")
        description = category_payload.get("description")
        distinguishing_traits = category_payload.get("distinguishing_traits", [])
        raw_subtechniques = category_payload.get("subtechniques", [])

        if not isinstance(name, str) or not name.strip():
            raise SystemExit("Each taxonomy category must have a non-empty name.")
        if not isinstance(description, str) or not description.strip():
            raise SystemExit(
                f"Taxonomy category '{name}' is missing a non-empty description."
            )
        if not isinstance(distinguishing_traits, list):
            raise SystemExit(
                f"Taxonomy category '{name}' has invalid distinguishing_traits."
            )
        if not isinstance(raw_subtechniques, list):
            raise SystemExit(f"Taxonomy category '{name}' has invalid subtechniques.")

        category_key = canonical_label(name)
        if category_key in taxonomy:
            raise SystemExit(f"Duplicate taxonomy category name detected: {name}")

        subtechniques: dict[str, str] = {}
        for subtechnique_payload in raw_subtechniques:
            if not isinstance(subtechnique_payload, dict):
                raise SystemExit(
                    f"Taxonomy category '{name}' contains a non-object subtechnique."
                )
            sub_name = subtechnique_payload.get("name")
            sub_description = subtechnique_payload.get("description")
            if not isinstance(sub_name, str) or not sub_name.strip():
                raise SystemExit(
                    f"Taxonomy category '{name}' has a subtechnique with no name."
                )
            if not isinstance(sub_description, str) or not sub_description.strip():
                raise SystemExit(
                    f"Taxonomy subtechnique '{sub_name}' in '{name}' needs a description."
                )
            sub_key = canonical_label(sub_name)
            if sub_key in subtechniques:
                raise SystemExit(
                    f"Duplicate subtechnique '{sub_name}' detected under '{name}'."
                )
            subtechniques[sub_key] = sub_name.strip()

        taxonomy[category_key] = TaxonomyCategory(
            name=name.strip(),
            description=description.strip(),
            distinguishing_traits=[
                trait.strip()
                for trait in distinguishing_traits
                if isinstance(trait, str) and trait.strip()
            ],
            subtechniques=subtechniques,
        )

    return taxonomy, compute_file_sha256(PROPOSED_TAXONOMY_PATH)


def count_normalized_records() -> int:
    if not NORMALIZED_PATH.exists():
        raise SystemExit(
            "Normalized corpus not found at data/corpus/normalized.jsonl. "
            "Run normalize_corpus.py before classify_corpus.py."
        )

    count = 0
    with NORMALIZED_PATH.open("r", encoding="utf-8") as normalized_file:
        for line in normalized_file:
            if line.strip():
                count += 1
    if count == 0:
        raise SystemExit("Normalized corpus is empty; cannot classify prompts.")
    return count


def load_normalized_record(payload: dict[str, Any], line_number: int) -> NormalizedRecord:
    try:
        prompt_id = payload["prompt_id"]
        source = payload["source"]
        source_file = payload["source_file"]
        source_row = payload["source_row"]
        text = payload["text"]
    except KeyError as error:
        raise SystemExit(
            f"Normalized record at line {line_number} is missing key: {error}"
        ) from error

    raw_fields = payload.get("raw_fields", {})
    if not all(
        [
            isinstance(prompt_id, str),
            isinstance(source, str),
            isinstance(source_file, str),
            isinstance(source_row, int),
            isinstance(text, str),
            isinstance(raw_fields, dict),
        ]
    ):
        raise SystemExit(
            f"Normalized record at line {line_number} has invalid field types."
        )

    return NormalizedRecord(
        prompt_id=prompt_id,
        source=source,
        source_file=source_file,
        source_row=source_row,
        text=text,
        raw_fields=raw_fields,
    )


def iter_normalized_records(
    *,
    start_index: int = 0,
    limit: int | None = None,
) -> Any:
    emitted = 0
    seen_records = 0
    with NORMALIZED_PATH.open("r", encoding="utf-8") as normalized_file:
        for line_number, line in enumerate(normalized_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue

            seen_records += 1
            if seen_records <= start_index:
                continue
            if limit is not None and emitted >= limit:
                return

            try:
                payload = json.loads(stripped_line)
            except json.JSONDecodeError as error:
                raise SystemExit(
                    f"Malformed normalized JSONL at line {line_number}: {error.msg}"
                ) from error

            if not isinstance(payload, dict):
                raise SystemExit(
                    f"Normalized record at line {line_number} is not a JSON object."
                )

            yield load_normalized_record(payload, line_number)
            emitted += 1


def count_staging_records() -> int:
    if not CLASSIFIED_STAGING_PATH.exists():
        return 0
    count = 0
    with CLASSIFIED_STAGING_PATH.open("r", encoding="utf-8") as staging_file:
        for line in staging_file:
            if line.strip():
                count += 1
    return count


def load_checkpoint() -> dict[str, Any] | None:
    if not CLASSIFICATION_CHECKPOINT_PATH.exists():
        return None
    with CLASSIFICATION_CHECKPOINT_PATH.open("r", encoding="utf-8") as checkpoint_file:
        payload = json.load(checkpoint_file)
    if not isinstance(payload, dict):
        raise SystemExit("Classification checkpoint is malformed.")
    return payload


def save_checkpoint(payload: dict[str, Any]) -> None:
    with CLASSIFICATION_CHECKPOINT_PATH.open("w", encoding="utf-8", newline="\n") as checkpoint:
        json.dump(payload, checkpoint, indent=2, ensure_ascii=False)
        checkpoint.write("\n")


def remove_path_if_exists(file_path: Path) -> None:
    if file_path.exists():
        file_path.unlink()


def prepare_run_state(
    *,
    total_records: int,
    normalized_sha256: str,
    taxonomy_sha256: str,
    restart: bool,
) -> dict[str, Any]:
    checkpoint = load_checkpoint()

    if restart:
        remove_path_if_exists(CLASSIFIED_STAGING_PATH)
        remove_path_if_exists(CLASSIFICATION_CHECKPOINT_PATH)
        remove_path_if_exists(CLASSIFICATION_FAILURE_LOG_PATH)
        checkpoint = None

    if checkpoint is None:
        if CLASSIFIED_STAGING_PATH.exists():
            raise SystemExit(
                "Found classified_staging.jsonl without a matching checkpoint. "
                "Use --restart to discard stale staging state before classifying again."
            )
        remove_path_if_exists(CLASSIFICATION_FAILURE_LOG_PATH)
        return {
            "run_started_at": now_utc_iso(),
            "normalized_path": str(NORMALIZED_PATH),
            "proposed_taxonomy_path": str(PROPOSED_TAXONOMY_PATH),
            "classified_path": str(CLASSIFIED_PATH),
            "classified_staging_path": str(CLASSIFIED_STAGING_PATH),
            "normalized_sha256": normalized_sha256,
            "taxonomy_sha256": taxonomy_sha256,
            "model": MODEL_NAME,
            "batch_size": BATCH_SIZE,
            "max_prompt_chars": MAX_PROMPT_CHARS,
            "max_batch_input_tokens": MAX_BATCH_INPUT_TOKENS,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "total_records": total_records,
            "processed_records": 0,
            "batches_completed": 0,
            "batch_retry_attempts": 0,
            "batches_split_for_token_pressure": 0,
            "records_classified_with_fallback": 0,
            "failure_events": 0,
            "token_usage": {
                "estimated_input_tokens": 0,
                "actual_input_tokens": 0,
                "actual_output_tokens": 0,
                "estimated_cost_usd": estimate_cost_usd(0, 0),
            },
            "last_updated_at": now_utc_iso(),
            "completed": False,
        }

    if checkpoint.get("normalized_sha256") != normalized_sha256:
        raise SystemExit(
            "Existing classification checkpoint does not match the current "
            "normalized.jsonl. Restart with --restart to begin a clean run."
        )
    if checkpoint.get("taxonomy_sha256") != taxonomy_sha256:
        raise SystemExit(
            "Existing classification checkpoint does not match the current "
            "proposed_taxonomy.json. Restart with --restart to begin a clean run."
        )

    staging_records = count_staging_records()
    checkpoint_records = safe_int(checkpoint.get("processed_records"), 0)
    if staging_records != checkpoint_records:
        safe_processed_records = min(staging_records, checkpoint_records)
        logger.warning(
            "Checkpoint/staging mismatch detected. checkpoint=%s staging=%s; resuming from %s completed records",
            checkpoint_records,
            staging_records,
            safe_processed_records,
        )
        checkpoint["processed_records"] = safe_processed_records
    checkpoint["total_records"] = total_records
    checkpoint["completed"] = False
    return checkpoint


def truncate_prompt(text: str) -> str:
    if len(text) <= MAX_PROMPT_CHARS:
        return text
    truncated = text[: MAX_PROMPT_CHARS - 3].rstrip()
    return f"{truncated}..."


def build_taxonomy_reference(taxonomy: dict[str, TaxonomyCategory]) -> str:
    lines = ["Approved taxonomy categories:"]
    for category in taxonomy.values():
        lines.append(f"- {category.name}: {category.description}")
        if category.distinguishing_traits:
            lines.append(
                "  distinguishing traits: "
                + "; ".join(category.distinguishing_traits[:6])
            )
        if category.subtechniques:
            lines.append(
                "  allowed subtechniques: "
                + "; ".join(category.subtechniques.values())
            )
    lines.append("")
    lines.append(
        "Allowed supporting traits: " + "; ".join(SUPPORTING_TRAIT_OPTIONS)
    )
    lines.append(
        f"Allowed fallback primary category when no approved category fits: {PRIMARY_FALLBACK_CATEGORY}"
    )
    return "\n".join(lines)


def build_batch_prompt(
    records: list[NormalizedRecord],
    taxonomy_reference: str,
) -> str:
    lines = [
        "Classify each prompt below using the approved taxonomy.",
        "",
        "Output requirements:",
        f"- primary_category must be one approved taxonomy category or {PRIMARY_FALLBACK_CATEGORY}.",
        "- subtechnique must be null unless an approved subtechnique under the chosen primary category clearly fits.",
        "- supporting_traits must only contain items from the allowed supporting-traits list.",
        "- confidence is a float from 0.0 to 1.0.",
        "- rationale must stay short and explain the dominant mechanism.",
        "",
        "Classification guidance:",
        "- Choose the mechanism that most directly drives the jailbreak attempt.",
        "- Do not select a secondary framing cue as the primary category if a stronger bypass mechanism is present.",
        "- Use supporting traits for research pretext, professional context, creative writing framing, persona support, fictional framing support, and similar secondary signals.",
        "",
        taxonomy_reference,
        "",
        "Prompts:",
    ]
    for record in records:
        lines.append(f"PROMPT_ID: {record.prompt_id}")
        lines.append("TEXT:")
        lines.append(truncate_prompt(record.text))
        lines.append("")
    return "\n".join(lines)


def estimate_request_input_tokens(
    client: Anthropic,
    user_prompt: str,
) -> int | None:
    try:
        token_estimate = client.messages.count_tokens(
            model=MODEL_NAME,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            output_format=BatchClassificationOutput,
        )
    except Exception as error:
        logger.warning("Could not estimate classification input tokens: %s", error)
        return None
    return token_estimate.input_tokens


def normalize_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def validate_classification_output(
    parsed_output: BatchClassificationOutput,
    records: list[NormalizedRecord],
    taxonomy: dict[str, TaxonomyCategory],
) -> dict[str, ClassificationResult]:
    expected_prompt_ids = {record.prompt_id for record in records}
    classification_lookup: dict[str, ClassificationResult] = {}

    for item in parsed_output.classifications:
        prompt_id = item.prompt_id.strip()
        if prompt_id not in expected_prompt_ids:
            raise ValueError(f"Unexpected prompt_id in model output: {prompt_id}")
        if prompt_id in classification_lookup:
            raise ValueError(f"Duplicate prompt_id in model output: {prompt_id}")

        primary_category = item.primary_category.strip()
        primary_key = canonical_label(primary_category)
        if primary_key == canonical_label(PRIMARY_FALLBACK_CATEGORY):
            resolved_primary_category = PRIMARY_FALLBACK_CATEGORY
            allowed_subtechniques: dict[str, str] = {}
        else:
            taxonomy_category = taxonomy.get(primary_key)
            if taxonomy_category is None:
                raise ValueError(
                    f"Model returned primary category outside approved taxonomy: {primary_category}"
                )
            resolved_primary_category = taxonomy_category.name
            allowed_subtechniques = taxonomy_category.subtechniques

        subtechnique = normalize_optional_string(item.subtechnique)
        if subtechnique is not None:
            subtechnique_key = canonical_label(subtechnique)
            if subtechnique_key not in allowed_subtechniques:
                raise ValueError(
                    f"Model returned invalid subtechnique '{subtechnique}' for category '{resolved_primary_category}'"
                )
            resolved_subtechnique = allowed_subtechniques[subtechnique_key]
        else:
            resolved_subtechnique = None

        supporting_traits: list[str] = []
        seen_traits: set[str] = set()
        for trait in item.supporting_traits:
            trait_name = trait.strip()
            if trait_name not in SUPPORTING_TRAIT_OPTIONS:
                raise ValueError(f"Model returned unsupported supporting trait: {trait_name}")
            if trait_name in seen_traits:
                continue
            seen_traits.add(trait_name)
            supporting_traits.append(trait_name)

        rationale = " ".join(item.rationale.split())
        if not rationale:
            raise ValueError("Model returned empty rationale.")

        classification_lookup[prompt_id] = ClassificationResult(
            primary_category=resolved_primary_category,
            subtechnique=resolved_subtechnique,
            supporting_traits=supporting_traits,
            confidence=round(min(max(item.confidence, 0.0), 1.0), 3),
            rationale=rationale[:240],
        )

    missing_prompt_ids = expected_prompt_ids.difference(classification_lookup)
    if missing_prompt_ids:
        raise ValueError(
            f"Model output omitted prompt_ids: {sorted(missing_prompt_ids)[:5]}"
        )

    return classification_lookup


def request_batch_classification(
    *,
    client: Anthropic,
    records: list[NormalizedRecord],
    taxonomy: dict[str, TaxonomyCategory],
    taxonomy_reference: str,
    checkpoint: dict[str, Any],
) -> BatchRequestResult:
    if not records:
        raise ValueError("Cannot classify an empty batch.")

    user_prompt = build_batch_prompt(records, taxonomy_reference)
    estimated_input_tokens = estimate_request_input_tokens(client, user_prompt)

    if (
        estimated_input_tokens is not None
        and estimated_input_tokens > MAX_BATCH_INPUT_TOKENS
        and len(records) > 1
    ):
        checkpoint["batches_split_for_token_pressure"] += 1
        midpoint = len(records) // 2
        logger.info(
            "Splitting batch of %s prompts because estimated input tokens %s exceeded limit %s",
            len(records),
            estimated_input_tokens,
            MAX_BATCH_INPUT_TOKENS,
        )
        left_result = request_batch_classification(
            client=client,
            records=records[:midpoint],
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            checkpoint=checkpoint,
        )
        right_result = request_batch_classification(
            client=client,
            records=records[midpoint:],
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            checkpoint=checkpoint,
        )
        combined = dict(left_result.classifications)
        combined.update(right_result.classifications)
        combined_attempt_count = left_result.attempt_count + right_result.attempt_count
        return BatchRequestResult(
            classifications=combined,
            estimated_input_tokens=(
                (left_result.estimated_input_tokens or 0)
                + (right_result.estimated_input_tokens or 0)
            ),
            actual_input_tokens=(
                left_result.actual_input_tokens + right_result.actual_input_tokens
            ),
            actual_output_tokens=(
                left_result.actual_output_tokens + right_result.actual_output_tokens
            ),
            stop_reason=None,
            attempt_count=combined_attempt_count,
        )

    prompt_ids = [record.prompt_id for record in records]
    last_error: Exception | None = None

    for attempt_number in range(1, MAX_RETRIES_PER_BATCH + 1):
        logger.info(
            "Classifying batch of %s prompts with model %s (attempt %s/%s, estimated input tokens=%s)",
            len(records),
            MODEL_NAME,
            attempt_number,
            MAX_RETRIES_PER_BATCH,
            estimated_input_tokens if estimated_input_tokens is not None else "unknown",
        )
        try:
            response = client.messages.parse(
                model=MODEL_NAME,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                output_format=BatchClassificationOutput,
            )
            if response.stop_reason == "max_tokens" or response.parsed_output is None:
                raise ValueError(
                    "Structured classification output was incomplete or missing."
                )

            classification_lookup = validate_classification_output(
                response.parsed_output,
                records,
                taxonomy,
            )
            return BatchRequestResult(
                classifications=classification_lookup,
                estimated_input_tokens=estimated_input_tokens,
                actual_input_tokens=response.usage.input_tokens,
                actual_output_tokens=response.usage.output_tokens,
                stop_reason=response.stop_reason,
                attempt_count=attempt_number,
            )
        except (ValidationError, ValueError) as error:
            last_error = error
            checkpoint["batch_retry_attempts"] += 1
            checkpoint["failure_events"] += 1
            debug_path = write_debug_payload(
                batch_prompt_ids=prompt_ids,
                response_stage="structured_output_validation_failure",
                error_message=str(error),
                response=locals().get("response"),
                estimated_input_tokens=estimated_input_tokens,
                extra_context={
                    "attempt_number": attempt_number,
                    "batch_size": len(records),
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                },
            )
            log_failure_event(
                {
                    "timestamp": now_utc_iso(),
                    "prompt_ids": prompt_ids,
                    "batch_size": len(records),
                    "attempt_number": attempt_number,
                    "failure_type": type(error).__name__,
                    "failure_stage": "structured_output_validation",
                    "debug_path": str(debug_path),
                    "message": str(error),
                }
            )
        except Exception as error:
            last_error = error
            checkpoint["batch_retry_attempts"] += 1
            checkpoint["failure_events"] += 1
            debug_path = write_debug_payload(
                batch_prompt_ids=prompt_ids,
                response_stage="structured_output_request_failure",
                error_message=str(error),
                estimated_input_tokens=estimated_input_tokens,
                extra_context={
                    "attempt_number": attempt_number,
                    "batch_size": len(records),
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                },
            )
            log_failure_event(
                {
                    "timestamp": now_utc_iso(),
                    "prompt_ids": prompt_ids,
                    "batch_size": len(records),
                    "attempt_number": attempt_number,
                    "failure_type": type(error).__name__,
                    "failure_stage": "structured_output_request",
                    "debug_path": str(debug_path),
                    "message": str(error),
                }
            )

        if attempt_number < MAX_RETRIES_PER_BATCH:
            sleep_seconds = RETRY_BASE_DELAY_SECONDS * attempt_number
            logger.warning(
                "Retrying batch after %ss due to %s: %s",
                sleep_seconds,
                type(last_error).__name__ if last_error else "error",
                last_error,
            )
            time.sleep(sleep_seconds)

    if len(records) > 1:
        midpoint = len(records) // 2
        logger.warning(
            "Falling back to recursive batch split after repeated failures for %s prompts",
            len(records),
        )
        left_result = request_batch_classification(
            client=client,
            records=records[:midpoint],
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            checkpoint=checkpoint,
        )
        right_result = request_batch_classification(
            client=client,
            records=records[midpoint:],
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            checkpoint=checkpoint,
        )
        combined = dict(left_result.classifications)
        combined.update(right_result.classifications)
        return BatchRequestResult(
            classifications=combined,
            estimated_input_tokens=(
                (left_result.estimated_input_tokens or 0)
                + (right_result.estimated_input_tokens or 0)
            ),
            actual_input_tokens=(
                left_result.actual_input_tokens + right_result.actual_input_tokens
            ),
            actual_output_tokens=(
                left_result.actual_output_tokens + right_result.actual_output_tokens
            ),
            stop_reason=None,
            attempt_count=left_result.attempt_count + right_result.attempt_count,
        )

    record = records[0]
    checkpoint["records_classified_with_fallback"] += 1
    log_failure_event(
        {
            "timestamp": now_utc_iso(),
            "prompt_ids": [record.prompt_id],
            "batch_size": 1,
            "attempt_number": MAX_RETRIES_PER_BATCH,
            "failure_type": type(last_error).__name__ if last_error else "UnknownError",
            "failure_stage": "fallback_applied",
            "message": str(last_error) if last_error else "Unknown classification failure",
        }
    )
    fallback_result = ClassificationResult(
        primary_category=PRIMARY_FALLBACK_CATEGORY,
        subtechnique=None,
        supporting_traits=[],
        confidence=0.0,
        rationale=FALLBACK_RATIONALE,
    )
    return BatchRequestResult(
        classifications={record.prompt_id: fallback_result},
        estimated_input_tokens=estimated_input_tokens,
        actual_input_tokens=0,
        actual_output_tokens=0,
        stop_reason="fallback_applied",
        attempt_count=MAX_RETRIES_PER_BATCH,
    )


def build_output_record(
    record: NormalizedRecord,
    classification: ClassificationResult,
) -> dict[str, Any]:
    return {
        "prompt_id": record.prompt_id,
        "source": record.source,
        "source_file": record.source_file,
        "source_row": record.source_row,
        "text": record.text,
        "raw_fields": record.raw_fields,
        "classification": {
            "primary_category": classification.primary_category,
            "subtechnique": classification.subtechnique,
            "supporting_traits": classification.supporting_traits,
            "confidence": classification.confidence,
            "rationale": classification.rationale,
        },
    }


def append_classified_records(records: list[dict[str, Any]]) -> None:
    with CLASSIFIED_STAGING_PATH.open("a", encoding="utf-8", newline="\n") as staging_file:
        for record in records:
            json.dump(record, staging_file, ensure_ascii=False)
            staging_file.write("\n")
        staging_file.flush()


def update_checkpoint_usage(
    checkpoint: dict[str, Any],
    batch_result: BatchRequestResult,
) -> None:
    usage = checkpoint.setdefault("token_usage", {})
    usage["estimated_input_tokens"] = safe_int(
        usage.get("estimated_input_tokens"), 0
    ) + safe_int(batch_result.estimated_input_tokens, 0)
    usage["actual_input_tokens"] = safe_int(
        usage.get("actual_input_tokens"), 0
    ) + batch_result.actual_input_tokens
    usage["actual_output_tokens"] = safe_int(
        usage.get("actual_output_tokens"), 0
    ) + batch_result.actual_output_tokens
    usage["estimated_cost_usd"] = estimate_cost_usd(
        usage["actual_input_tokens"],
        usage["actual_output_tokens"],
    )


def classify_corpus(*, limit: int | None, restart: bool) -> dict[str, Any]:
    if not NORMALIZED_PATH.exists():
        raise SystemExit(
            "Normalized corpus not found at data/corpus/normalized.jsonl. "
            "Run normalize_corpus.py before classify_corpus.py."
        )

    taxonomy, taxonomy_sha256 = load_taxonomy()
    normalized_sha256 = compute_file_sha256(NORMALIZED_PATH)
    total_records = count_normalized_records()
    effective_total_records = min(total_records, limit) if limit is not None else total_records

    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
    checkpoint = prepare_run_state(
        total_records=effective_total_records,
        normalized_sha256=normalized_sha256,
        taxonomy_sha256=taxonomy_sha256,
        restart=restart,
    )
    taxonomy_reference = build_taxonomy_reference(taxonomy)
    client = get_anthropic_client()

    processed_records = safe_int(checkpoint.get("processed_records"), 0)
    if processed_records > effective_total_records:
        raise SystemExit(
            "Checkpoint processed_records exceeds the requested run limit. "
            "Restart with --restart or increase the limit."
        )

    batch_buffer: list[NormalizedRecord] = []
    batch_counter = safe_int(checkpoint.get("batches_completed"), 0)

    logger.info(
        "Starting classification run over %s normalized records using %s taxonomy categories; resuming at record %s",
        effective_total_records,
        len(taxonomy),
        processed_records,
    )

    for record in iter_normalized_records(
        start_index=processed_records,
        limit=None if limit is None else effective_total_records - processed_records,
    ):
        batch_buffer.append(record)
        if len(batch_buffer) < BATCH_SIZE:
            continue

        batch_counter += 1
        batch_result = request_batch_classification(
            client=client,
            records=batch_buffer,
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            checkpoint=checkpoint,
        )
        output_records = [
            build_output_record(record, batch_result.classifications[record.prompt_id])
            for record in batch_buffer
        ]
        append_classified_records(output_records)

        processed_records += len(batch_buffer)
        checkpoint["processed_records"] = processed_records
        checkpoint["batches_completed"] = batch_counter
        checkpoint["last_updated_at"] = now_utc_iso()
        update_checkpoint_usage(checkpoint, batch_result)

        if batch_counter % CHECKPOINT_EVERY_BATCHES == 0:
            save_checkpoint(checkpoint)

        logger.info(
            "Classified %s/%s records; batch size=%s; cumulative input tokens=%s; cumulative output tokens=%s; estimated cost=%s",
            processed_records,
            effective_total_records,
            len(output_records),
            checkpoint["token_usage"]["actual_input_tokens"],
            checkpoint["token_usage"]["actual_output_tokens"],
            checkpoint["token_usage"]["estimated_cost_usd"],
        )
        batch_buffer = []

    if batch_buffer:
        batch_counter += 1
        batch_result = request_batch_classification(
            client=client,
            records=batch_buffer,
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            checkpoint=checkpoint,
        )
        output_records = [
            build_output_record(record, batch_result.classifications[record.prompt_id])
            for record in batch_buffer
        ]
        append_classified_records(output_records)

        processed_records += len(batch_buffer)
        checkpoint["processed_records"] = processed_records
        checkpoint["batches_completed"] = batch_counter
        checkpoint["last_updated_at"] = now_utc_iso()
        update_checkpoint_usage(checkpoint, batch_result)
        save_checkpoint(checkpoint)

        logger.info(
            "Classified %s/%s records; batch size=%s; cumulative input tokens=%s; cumulative output tokens=%s; estimated cost=%s",
            processed_records,
            effective_total_records,
            len(output_records),
            checkpoint["token_usage"]["actual_input_tokens"],
            checkpoint["token_usage"]["actual_output_tokens"],
            checkpoint["token_usage"]["estimated_cost_usd"],
        )

    if processed_records != effective_total_records:
        raise SystemExit(
            f"Classification completed {processed_records} records but expected {effective_total_records}."
        )

    if limit is None:
        CLASSIFIED_STAGING_PATH.replace(CLASSIFIED_PATH)
    else:
        logger.info(
            "Dry-run limit active; leaving partial results in staging file %s and not replacing %s",
            CLASSIFIED_STAGING_PATH,
            CLASSIFIED_PATH,
        )

    checkpoint["completed"] = True
    checkpoint["last_updated_at"] = now_utc_iso()
    save_checkpoint(checkpoint)

    return {
        "classified_path": str(CLASSIFIED_PATH),
        "classified_staging_path": str(CLASSIFIED_STAGING_PATH),
        "processed_records": processed_records,
        "total_records": effective_total_records,
        "token_usage": checkpoint["token_usage"],
        "batch_retry_attempts": checkpoint["batch_retry_attempts"],
        "batches_split_for_token_pressure": checkpoint["batches_split_for_token_pressure"],
        "records_classified_with_fallback": checkpoint["records_classified_with_fallback"],
        "failure_events": checkpoint["failure_events"],
        "limit": limit,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply the approved RedLib taxonomy across normalized prompts and "
            "write data/corpus/classified.jsonl."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Classify only the first N normalized records for a partial verification run.",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Discard existing classification staging/checkpoint files and restart the run.",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    result = classify_corpus(limit=args.limit, restart=args.restart)
    logger.info(
        "Classification finished for %s/%s records. input_tokens=%s output_tokens=%s retries=%s fallback_records=%s failure_events=%s",
        result["processed_records"],
        result["total_records"],
        result["token_usage"]["actual_input_tokens"],
        result["token_usage"]["actual_output_tokens"],
        result["batch_retry_attempts"],
        result["records_classified_with_fallback"],
        result["failure_events"],
    )
    if result["limit"] is None:
        logger.info("Final classified corpus written to %s", CLASSIFIED_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
