import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from pydantic import BaseModel, Field, ValidationError
except ImportError:  # pragma: no cover - fallback for syntax-only checks
    class ValidationError(Exception):
        """Fallback placeholder used when pydantic is unavailable."""


    class BaseModel:
        """Fallback placeholder used when pydantic is unavailable."""

        @classmethod
        def model_json_schema(cls) -> dict[str, Any]:
            raise ImportError(
                "pydantic is required to run corpus.reclassify_unclear. "
                "Install project dependencies before executing this module."
            )


    def Field(default: Any = None, **kwargs: Any) -> Any:
        return default

logger = logging.getLogger(__name__)

CORPUS_ROOT = Path("data") / "corpus"
UNCLEAR_RECORDS_PATH = CORPUS_ROOT / "unclear_records.jsonl"
UNCLEAR_RECLASSIFIED_PATH = CORPUS_ROOT / "unclear_reclassified.jsonl"
UNCLEAR_RECLASSIFIED_STAGING_PATH = CORPUS_ROOT / "unclear_reclassified.staging.jsonl"
CLASSIFIED_CONFIRMED_PATH = CORPUS_ROOT / "classified_confirmed.jsonl"
CLASSIFIED_FINAL_PATH = CORPUS_ROOT / "classified_final.jsonl"
CLASSIFIED_FINAL_STAGING_PATH = CORPUS_ROOT / "classified_final.staging.jsonl"
PROPOSED_TAXONOMY_PATH = CORPUS_ROOT / "proposed_taxonomy.json"
DEBUG_DIR = CORPUS_ROOT / "reclassify_unclear_debug"

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5"
MODEL_NAME = os.environ.get("REDLIB_CLASSIFY_MODEL", DEFAULT_ANTHROPIC_MODEL)
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
RATIONALE_SCHEMA_MAX_CHARS = 300

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
SUPPORTING_TRAITS_CLOSED_VOCABULARY = "; ".join(
    f'"{trait}"' for trait in SUPPORTING_TRAIT_OPTIONS
)

SYSTEM_PROMPT = """You classify jailbreak prompts against an approved operational taxonomy.

Your job is to assign one dominant primary jailbreak mechanism per prompt.

Hard rules:
- Return structured output only.
- Return batch_index values only for prompt identity. Do not return prompt_id values.
- Choose exactly one primary category from the provided list, or the explicit fallback category when no approved category fits.
- Do not invent new primary categories, subtechniques, or supporting traits.
- Primary category means the mechanism that most directly contributes to bypassing model safety behavior.
- Supporting traits are secondary signals only. Do not promote a secondary trait into the primary category unless it is the main bypass mechanism.
- If multiple mechanisms appear, choose the single dominant one and use supporting traits for the rest.
- supporting_traits is a closed vocabulary. The only allowed values are provided in the user prompt.
- Do not put taxonomy category names in supporting_traits.
- Do not put subtechnique names in supporting_traits.
- Do not paraphrase or partially rewrite supporting trait labels.
- If no exact supporting trait applies, return an empty list.
- Prefer fewer supporting traits over speculative or invalid supporting traits.
- Rationale must be exactly one concise sentence.
- Use objective language only.
- Keep rationale at 120 characters or fewer.
- Explain only the dominant classification decision.
- Do not add extra justification, caveats, or discussion.
- Do not reproduce or quote long prompt text.
"""


class PromptClassificationOutput(BaseModel):
    batch_index: int = Field(ge=0)
    primary_category: str = Field(min_length=1)
    subtechnique: str | None = None
    supporting_traits: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=RATIONALE_SCHEMA_MAX_CHARS)


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


@dataclass
class ProgressStats:
    processed_records: int = 0
    retries: int = 0
    fallbacks: int = 0
    failure_events: int = 0
    batches_split_for_token_pressure: int = 0
    actual_input_tokens: int = 0
    actual_output_tokens: int = 0


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_label(value: str) -> str:
    return " ".join(value.strip().lower().split())


def compute_file_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_anthropic_client() -> Any:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Run with Doppler or export the key before reclassify_unclear.py."
        )
    try:
        from anthropic import Anthropic
    except ImportError as error:
        raise SystemExit(
            "anthropic package is not installed. Install project dependencies before "
            "running reclassify_unclear.py."
        ) from error
    return Anthropic(api_key=api_key)


def extract_text_content(response: Any) -> str:
    text_parts = []
    for block in getattr(response, "content", []):
        block_text = getattr(block, "text", None)
        if block_text:
            text_parts.append(block_text)
    if text_parts:
        return "\n".join(text_parts).strip()
    return ""


def write_debug_payload(
    *,
    batch_prompt_ids: list[str],
    response_stage: str,
    error_message: str,
    response: Any | None = None,
    estimated_input_tokens: int | None = None,
    extra_context: dict[str, Any] | None = None,
) -> Path:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prompt_stub = batch_prompt_ids[0] if batch_prompt_ids else "batch"
    debug_path = DEBUG_DIR / f"{prompt_stub}_{response_stage}_{timestamp}.json"
    payload = {
        "generated_at": now_utc_iso(),
        "model": MODEL_NAME,
        "batch_prompt_ids": batch_prompt_ids,
        "response_stage": response_stage,
        "error": error_message,
        "estimated_input_tokens": estimated_input_tokens,
        "stop_reason": getattr(response, "stop_reason", None) if response else None,
        "usage": {
            "input_tokens": getattr(getattr(response, "usage", None), "input_tokens", None),
            "output_tokens": getattr(getattr(response, "usage", None), "output_tokens", None),
        }
        if response
        else None,
        "raw_response": extract_text_content(response) if response else "",
        "extra_context": extra_context or {},
    }
    with debug_path.open("w", encoding="utf-8", newline="\n") as debug_file:
        json.dump(payload, debug_file, indent=2, ensure_ascii=False)
        debug_file.write("\n")
    return debug_path


def load_taxonomy() -> tuple[dict[str, TaxonomyCategory], str]:
    if not PROPOSED_TAXONOMY_PATH.exists():
        raise SystemExit(
            "Proposed taxonomy not found at data/corpus/proposed_taxonomy.json. "
            "Run corpus/discover_taxonomy.py before reclassify_unclear.py."
        )

    with PROPOSED_TAXONOMY_PATH.open("r", encoding="utf-8") as taxonomy_file:
        payload = json.load(taxonomy_file)

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


def load_unclear_record(payload: dict[str, Any], line_number: int) -> NormalizedRecord:
    try:
        prompt_id = payload["prompt_id"]
        source = payload["source"]
        source_file = payload["source_file"]
        source_row = payload["source_row"]
        text = payload["text"]
    except KeyError as error:
        raise SystemExit(
            f"Unclear record at line {line_number} is missing key: {error}"
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
            f"Unclear record at line {line_number} has invalid field types."
        )

    return NormalizedRecord(
        prompt_id=prompt_id,
        source=source,
        source_file=source_file,
        source_row=source_row,
        text=text,
        raw_fields=raw_fields,
    )


def iter_unclear_records() -> Any:
    if not UNCLEAR_RECORDS_PATH.exists():
        raise SystemExit(
            "Unclear records not found at data/corpus/unclear_records.jsonl."
        )

    with UNCLEAR_RECORDS_PATH.open("r", encoding="utf-8") as unclear_file:
        for line_number, line in enumerate(unclear_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue

            try:
                payload = json.loads(stripped_line)
            except json.JSONDecodeError as error:
                raise SystemExit(
                    f"Malformed unclear_records JSONL at line {line_number}: {error.msg}"
                ) from error

            if not isinstance(payload, dict):
                raise SystemExit(
                    f"Unclear record at line {line_number} is not a JSON object."
                )

            yield load_unclear_record(payload, line_number)


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
        "Allowed supporting traits (closed vocabulary, exact labels only): "
        + "; ".join(SUPPORTING_TRAIT_OPTIONS)
    )
    lines.append(
        f"Allowed fallback primary category when no approved category fits: {PRIMARY_FALLBACK_CATEGORY}"
    )
    return "\n".join(lines)


def truncate_prompt(text: str, max_prompt_chars: int) -> str:
    if len(text) <= max_prompt_chars:
        return text
    truncated = text[: max_prompt_chars - 3].rstrip()
    return f"{truncated}..."


def build_batch_prompt(records: list[NormalizedRecord], taxonomy_reference: str) -> str:
    lines = [
        "Classify each prompt below using the approved taxonomy.",
        "",
        "Output requirements:",
        "- batch_index must be the numeric INDEX for that prompt.",
        "- Do not return prompt_id values.",
        f"- primary_category must be one approved taxonomy category or {PRIMARY_FALLBACK_CATEGORY}.",
        "- subtechnique must be null unless an approved subtechnique under the chosen primary category clearly fits.",
        "- supporting_traits is a closed list of exact labels, not an open tagging field.",
        f"- supporting_traits may only contain these exact labels: {SUPPORTING_TRAITS_CLOSED_VOCABULARY}.",
        "- supporting_traits must not contain taxonomy category names.",
        "- supporting_traits must not contain subtechnique names.",
        "- supporting_traits must not paraphrase, shorten, or combine allowed labels.",
        "- If no exact supporting trait applies, supporting_traits must be an empty list.",
        "- Prefer fewer supporting traits over invalid or speculative supporting traits.",
        "- confidence is a float from 0.0 to 1.0.",
        "- rationale must be one concise objective sentence.",
        "- rationale must be at most 120 characters.",
        "- rationale must explain only the dominant classification decision.",
        "- rationale must not include extra justification or discussion.",
        "",
        "Classification guidance:",
        "- Choose the mechanism that most directly drives the jailbreak attempt.",
        "- Do not select a secondary framing cue as the primary category if a stronger bypass mechanism is present.",
        "- Use supporting traits only for exact matches to the allowed secondary-signal labels.",
        "- If a secondary mechanism looks like another taxonomy category or subtechnique, keep it out of supporting_traits.",
        "",
        taxonomy_reference,
        "",
        "Prompts:",
    ]
    for batch_index, record in enumerate(records):
        lines.append(f"INDEX: {batch_index}")
        lines.append("TEXT:")
        lines.append(truncate_prompt(record.text, MAX_PROMPT_CHARS))
        lines.append("")
    return "\n".join(lines)


def estimate_request_input_tokens(client: Any, user_prompt: str) -> int | None:
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
    expected_batch_indices = set(range(len(records)))
    batch_index_to_record = {
        batch_index: record for batch_index, record in enumerate(records)
    }
    classification_lookup: dict[str, ClassificationResult] = {}
    seen_batch_indices: set[int] = set()

    for item in parsed_output.classifications:
        batch_index = item.batch_index
        if batch_index not in expected_batch_indices:
            raise ValueError(f"Unexpected batch_index in model output: {batch_index}")
        if batch_index in seen_batch_indices:
            raise ValueError(f"Duplicate batch_index in model output: {batch_index}")
        seen_batch_indices.add(batch_index)
        prompt_id = batch_index_to_record[batch_index].prompt_id

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
                logger.warning(
                    "Dropping invalid subtechnique '%s' for category '%s' on prompt_id=%s",
                    subtechnique,
                    resolved_primary_category,
                    prompt_id,
                )
                resolved_subtechnique = None
            else:
                resolved_subtechnique = allowed_subtechniques[subtechnique_key]
        else:
            resolved_subtechnique = None

        supporting_traits: list[str] = []
        seen_traits: set[str] = set()
        for trait in item.supporting_traits:
            trait_name = trait.strip()
            if trait_name not in SUPPORTING_TRAIT_OPTIONS:
                logger.warning(
                    "Dropping unsupported supporting trait '%s' on prompt_id=%s",
                    trait_name,
                    prompt_id,
                )
                continue
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
            rationale=rationale,
        )

    missing_batch_indices = expected_batch_indices.difference(seen_batch_indices)
    if missing_batch_indices:
        raise ValueError(
            f"Model output omitted batch_indices: {sorted(missing_batch_indices)[:5]}"
        )

    return classification_lookup


def request_batch_classification(
    *,
    client: Any,
    records: list[NormalizedRecord],
    taxonomy: dict[str, TaxonomyCategory],
    taxonomy_reference: str,
    progress: ProgressStats,
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
        progress.batches_split_for_token_pressure += 1
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
            progress=progress,
        )
        right_result = request_batch_classification(
            client=client,
            records=records[midpoint:],
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            progress=progress,
        )
        combined = dict(left_result.classifications)
        combined.update(right_result.classifications)
        return BatchRequestResult(
            classifications=combined,
            estimated_input_tokens=(left_result.estimated_input_tokens or 0)
            + (right_result.estimated_input_tokens or 0),
            actual_input_tokens=left_result.actual_input_tokens
            + right_result.actual_input_tokens,
            actual_output_tokens=left_result.actual_output_tokens
            + right_result.actual_output_tokens,
            stop_reason=None,
            attempt_count=left_result.attempt_count + right_result.attempt_count,
        )

    prompt_ids = [record.prompt_id for record in records]
    last_error: Exception | None = None

    for attempt_number in range(1, MAX_RETRIES_PER_BATCH + 1):
        logger.info(
            "Classifying unclear batch of %s prompts with model %s (attempt %s/%s, estimated input tokens=%s)",
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
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt,
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                    }
                ],
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
            progress.retries += 1
            progress.failure_events += 1
            write_debug_payload(
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
        except Exception as error:
            last_error = error
            progress.retries += 1
            progress.failure_events += 1
            write_debug_payload(
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

        if attempt_number < MAX_RETRIES_PER_BATCH:
            sleep_seconds = RETRY_BASE_DELAY_SECONDS * attempt_number
            logger.warning(
                "Retrying unclear batch after %ss due to %s: %s",
                sleep_seconds,
                type(last_error).__name__ if last_error else "error",
                last_error,
            )
            time.sleep(sleep_seconds)

    if len(records) > 1:
        midpoint = len(records) // 2
        logger.warning(
            "Falling back to recursive batch split after repeated failures for %s unclear prompts",
            len(records),
        )
        left_result = request_batch_classification(
            client=client,
            records=records[:midpoint],
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            progress=progress,
        )
        right_result = request_batch_classification(
            client=client,
            records=records[midpoint:],
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            progress=progress,
        )
        combined = dict(left_result.classifications)
        combined.update(right_result.classifications)
        return BatchRequestResult(
            classifications=combined,
            estimated_input_tokens=(left_result.estimated_input_tokens or 0)
            + (right_result.estimated_input_tokens or 0),
            actual_input_tokens=left_result.actual_input_tokens
            + right_result.actual_input_tokens,
            actual_output_tokens=left_result.actual_output_tokens
            + right_result.actual_output_tokens,
            stop_reason=None,
            attempt_count=left_result.attempt_count + right_result.attempt_count,
        )

    record = records[0]
    progress.fallbacks += 1
    fallback_result = ClassificationResult(
        primary_category=PRIMARY_FALLBACK_CATEGORY,
        subtechnique=None,
        supporting_traits=[],
        confidence=0.0,
        rationale=FALLBACK_RATIONALE,
    )
    logger.warning(
        "Applying fallback classification to prompt_id=%s after repeated failures: %s",
        record.prompt_id,
        last_error,
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


def write_jsonl_atomic(output_path: Path, staging_path: Path, records: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with staging_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            json.dump(record, handle, ensure_ascii=False)
            handle.write("\n")
    if output_path.exists():
        output_path.unlink()
    staging_path.replace(output_path)


def reclassify_unclear_records() -> tuple[list[dict[str, Any]], ProgressStats]:
    taxonomy, _ = load_taxonomy()
    taxonomy_reference = build_taxonomy_reference(taxonomy)
    client = get_anthropic_client()
    progress = ProgressStats()
    input_records = list(iter_unclear_records())
    output_records: list[dict[str, Any]] = []

    logger.info(
        "Starting unclear-record reclassification over %s prompts using model=%s",
        len(input_records),
        MODEL_NAME,
    )

    for batch_start in range(0, len(input_records), BATCH_SIZE):
        batch_records = input_records[batch_start : batch_start + BATCH_SIZE]
        batch_result = request_batch_classification(
            client=client,
            records=batch_records,
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            progress=progress,
        )
        progress.actual_input_tokens += batch_result.actual_input_tokens
        progress.actual_output_tokens += batch_result.actual_output_tokens

        output_batch = [
            build_output_record(record, batch_result.classifications[record.prompt_id])
            for record in batch_records
        ]
        output_records.extend(output_batch)
        progress.processed_records += len(output_batch)

        logger.info(
            "Processed %s/%s unclear records; retries=%s; fallbacks=%s",
            progress.processed_records,
            len(input_records),
            progress.retries,
            progress.fallbacks,
        )

    write_jsonl_atomic(
        UNCLEAR_RECLASSIFIED_PATH,
        UNCLEAR_RECLASSIFIED_STAGING_PATH,
        output_records,
    )
    return output_records, progress


def load_jsonl_records(file_path: Path) -> list[dict[str, Any]]:
    if not file_path.exists():
        raise SystemExit(f"Required file not found: {file_path}")

    records: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue
            try:
                payload = json.loads(stripped_line)
            except json.JSONDecodeError as error:
                raise SystemExit(
                    f"Malformed JSONL in {file_path} at line {line_number}: {error.msg}"
                ) from error
            if not isinstance(payload, dict):
                raise SystemExit(
                    f"Record in {file_path} at line {line_number} is not a JSON object."
                )
            records.append(payload)
    return records


def merge_final_corpus(
    unclear_reclassified_records: list[dict[str, Any]],
) -> dict[str, int]:
    confirmed_records = load_jsonl_records(CLASSIFIED_CONFIRMED_PATH)
    successful_reclassified = [
        record
        for record in unclear_reclassified_records
        if record.get("classification", {}).get("primary_category")
        != PRIMARY_FALLBACK_CATEGORY
    ]
    still_unclear = len(unclear_reclassified_records) - len(successful_reclassified)

    merged_records = list(confirmed_records) + successful_reclassified
    write_jsonl_atomic(
        CLASSIFIED_FINAL_PATH,
        CLASSIFIED_FINAL_STAGING_PATH,
        merged_records,
    )

    return {
        "classified_confirmed_records": len(confirmed_records),
        "unclear_reclassified_successfully": len(successful_reclassified),
        "unclear_still_unclear": still_unclear,
        "classified_final_records": len(merged_records),
    }


def main() -> int:
    configure_logging()
    started_at = time.perf_counter()
    unclear_reclassified_records, progress = reclassify_unclear_records()
    merge_report = merge_final_corpus(unclear_reclassified_records)
    runtime_seconds = time.perf_counter() - started_at

    print(f"classified_confirmed records: {merge_report['classified_confirmed_records']}")
    print(
        "unclear records reclassified successfully: "
        f"{merge_report['unclear_reclassified_successfully']}"
    )
    print(
        "unclear records still Unclear after retry: "
        f"{merge_report['unclear_still_unclear']}"
    )
    print(f"total records in classified_final.jsonl: {merge_report['classified_final_records']}")
    print(f"records processed: {progress.processed_records}")
    print(f"retries: {progress.retries}")
    print(f"fallbacks: {progress.fallbacks}")
    print(f"runtime_seconds: {runtime_seconds:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
