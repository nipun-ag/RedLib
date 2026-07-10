import argparse
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .corpus_sampling import NormalizedRecord, select_stratified_sample

try:
    from pydantic import BaseModel, Field, ValidationError
except ImportError:  # pragma: no cover - fallback for structure-only imports
    class ValidationError(Exception):
        """Fallback placeholder used when pydantic is unavailable."""


    class BaseModel:
        """Fallback placeholder used when pydantic is unavailable."""

        @classmethod
        def model_json_schema(cls) -> dict[str, Any]:
            raise ImportError(
                "pydantic is required to run corpus.classify_corpus. "
                "Install project dependencies before executing this module."
            )

        def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise ImportError(
                "pydantic is required to run corpus.classify_corpus. "
                "Install project dependencies before executing this module."
            )


    def Field(default: Any = None, **kwargs: Any) -> Any:
        return default

if TYPE_CHECKING:
    from anthropic import Anthropic

logger = logging.getLogger(__name__)

CORPUS_ROOT = Path("data") / "corpus"
NORMALIZED_PATH = CORPUS_ROOT / "normalized.jsonl"
PROPOSED_TAXONOMY_PATH = CORPUS_ROOT / "proposed_taxonomy.json"
CLASSIFIED_PATH = CORPUS_ROOT / "classified.jsonl"
CLASSIFIED_STAGING_PATH = CORPUS_ROOT / "classified_staging.jsonl"
CLASSIFICATION_CHECKPOINT_PATH = CORPUS_ROOT / "classified_checkpoint.json"
CLASSIFICATION_FAILURE_LOG_PATH = CORPUS_ROOT / "classification_failures.jsonl"
CLASSIFICATION_DEBUG_DIR = CORPUS_ROOT / "classification_debug"

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5"
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
RATIONALE_SCHEMA_MAX_CHARS = 300
EXPERIMENT_SAMPLE_SEED = "redlib-classify-experiment-v1"

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
SUPPORTING_TRAITS = SUPPORTING_TRAIT_OPTIONS
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


@dataclass(frozen=True)
class RunConfig:
    batch_size: int
    max_prompt_chars: int
    experiment_name: str | None = None
    sample_size: int | None = None
    min_per_source: int = 40
    max_source_share: float = 0.4
    regenerate_sample: bool = False

    @property
    def is_experiment(self) -> bool:
        return self.experiment_name is not None


@dataclass(frozen=True)
class RunArtifacts:
    classified_path: Path
    staging_path: Path
    checkpoint_path: Path
    failure_log_path: Path
    debug_dir: Path
    summary_path: Path | None = None


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


MODEL_NAME = os.environ.get("REDLIB_CLASSIFY_MODEL", DEFAULT_ANTHROPIC_MODEL)


def get_anthropic_client() -> Any:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Run with Doppler or export the key before classify_corpus.py."
        )
    try:
        from anthropic import Anthropic
    except ImportError as error:
        raise SystemExit(
            "anthropic package is not installed. Install project dependencies before "
            "running classify_corpus.py with the Anthropic provider."
        ) from error
    return Anthropic(api_key=api_key)


def get_client() -> Any:
    return get_anthropic_client()


def sanitize_path_fragment(value: str) -> str:
    sanitized = "".join(
        character.lower()
        if character.isalnum() or character in {"-", "_"}
        else "-"
        for character in value.strip()
    )
    sanitized = "-".join(part for part in sanitized.split("-") if part)
    return sanitized or "experiment"


def build_run_artifacts(
    *,
    limit: int | None,
    run_config: RunConfig,
) -> RunArtifacts:
    if not run_config.is_experiment:
        return RunArtifacts(
            classified_path=CLASSIFIED_PATH,
            staging_path=CLASSIFIED_STAGING_PATH,
            checkpoint_path=CLASSIFICATION_CHECKPOINT_PATH,
            failure_log_path=CLASSIFICATION_FAILURE_LOG_PATH,
            debug_dir=CLASSIFICATION_DEBUG_DIR,
        )

    experiments_root = CORPUS_ROOT / "experiments"
    if run_config.sample_size is not None:
        limit_label = f"sample{run_config.sample_size}"
    else:
        limit_label = f"limit{limit}" if limit is not None else "limitall"
    experiment_label = sanitize_path_fragment(run_config.experiment_name or "experiment")
    stem = (
        f"classified_{experiment_label}_{limit_label}"
        f"_chars{run_config.max_prompt_chars}_batch{run_config.batch_size}"
    )
    return RunArtifacts(
        classified_path=experiments_root / f"{stem}.jsonl",
        staging_path=experiments_root / f"{stem}.staging.jsonl",
        checkpoint_path=experiments_root / f"{stem}.checkpoint.json",
        failure_log_path=experiments_root / f"{stem}.failures.jsonl",
        debug_dir=experiments_root / f"{stem}.debug",
        summary_path=experiments_root / f"{stem}.summary.json",
    )


def extract_text_content(response: Any) -> str:
    text_parts = []
    for block in getattr(response, "content", []):
        block_text = getattr(block, "text", None)
        if block_text:
            text_parts.append(block_text)
    if text_parts:
        return "\n".join(text_parts).strip()

    choices = getattr(response, "choices", None)
    if isinstance(choices, list):
        for choice in choices:
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None)
            if isinstance(content, str) and content.strip():
                text_parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        item_text = item.get("text")
                    else:
                        item_text = getattr(item, "text", None)
                    if isinstance(item_text, str) and item_text.strip():
                        text_parts.append(item_text)
    return "\n".join(text_parts).strip()


def extract_usage_metrics(response: Any) -> dict[str, int | None] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    input_tokens = getattr(usage, "input_tokens", None)
    if input_tokens is None:
        input_tokens = getattr(usage, "prompt_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    if output_tokens is None:
        output_tokens = getattr(usage, "completion_tokens", None)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def write_debug_payload(
    *,
    artifacts: RunArtifacts,
    batch_prompt_ids: list[str],
    response_stage: str,
    error_message: str,
    response: Any | None = None,
    estimated_input_tokens: int | None = None,
    extra_context: dict[str, Any] | None = None,
    model_name: str | None = None,
) -> Path:
    artifacts.debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prompt_stub = batch_prompt_ids[0] if batch_prompt_ids else "batch"
    debug_path = artifacts.debug_dir / f"{prompt_stub}_{response_stage}_{timestamp}.json"
    payload = {
        "generated_at": now_utc_iso(),
        "model": model_name,
        "batch_prompt_ids": batch_prompt_ids,
        "response_stage": response_stage,
        "error": error_message,
        "estimated_input_tokens": estimated_input_tokens,
        "stop_reason": getattr(response, "stop_reason", None) if response else None,
        "usage": extract_usage_metrics(response) if response else None,
        "raw_response": extract_text_content(response) if response else "",
        "extra_context": extra_context or {},
    }
    with debug_path.open("w", encoding="utf-8", newline="\n") as debug_file:
        json.dump(payload, debug_file, indent=2, ensure_ascii=False)
        debug_file.write("\n")
    return debug_path


def log_failure_event(artifacts: RunArtifacts, event: dict[str, Any]) -> None:
    artifacts.failure_log_path.parent.mkdir(parents=True, exist_ok=True)
    with artifacts.failure_log_path.open("a", encoding="utf-8", newline="\n") as log:
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
    prompt_id_filter: set[str] | None = None,
) -> Any:
    emitted = 0
    eligible_records = 0
    with NORMALIZED_PATH.open("r", encoding="utf-8") as normalized_file:
        for line_number, line in enumerate(normalized_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue

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

            record = load_normalized_record(payload, line_number)
            if prompt_id_filter is not None and record.prompt_id not in prompt_id_filter:
                continue

            eligible_records += 1
            if eligible_records <= start_index:
                continue
            if limit is not None and emitted >= limit:
                return

            yield record
            emitted += 1


def sample_prompt_ids_digest(prompt_ids: list[str]) -> str:
    return hashlib.sha256("\n".join(prompt_ids).encode("utf-8")).hexdigest()


def sample_cache_path(sample_size: int) -> Path:
    return CORPUS_ROOT / "experiments" / "samples" / f"sample_{sample_size}.json"


def load_experiment_sample_payload(sample_path: Path) -> dict[str, Any]:
    with sample_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"Sample file is malformed: {sample_path}")
    prompt_ids = payload.get("prompt_ids")
    if not isinstance(prompt_ids, list) or any(
        not isinstance(prompt_id, str) or not prompt_id for prompt_id in prompt_ids
    ):
        raise SystemExit(f"Sample file has invalid prompt_ids: {sample_path}")
    return payload


def generate_experiment_sample_payload(
    *,
    normalized_sha256: str,
    run_config: RunConfig,
) -> dict[str, Any]:
    records = list(iter_normalized_records())
    sample = select_stratified_sample(
        records=records,
        sample_size=run_config.sample_size or 0,
        min_per_source=run_config.min_per_source,
        max_source_share=run_config.max_source_share,
        seed=EXPERIMENT_SAMPLE_SEED,
    )
    prompt_ids = [record.prompt_id for record in sample]
    source_counts: dict[str, int] = {}
    for record in sample:
        source_counts[record.source] = source_counts.get(record.source, 0) + 1
    return {
        "generated_at": now_utc_iso(),
        "normalized_sha256": normalized_sha256,
        "sample_size": run_config.sample_size,
        "min_per_source": run_config.min_per_source,
        "max_source_share": run_config.max_source_share,
        "seed": EXPERIMENT_SAMPLE_SEED,
        "source_counts": dict(sorted(source_counts.items())),
        "prompt_ids": prompt_ids,
    }


def load_or_create_experiment_sample(
    *,
    normalized_sha256: str,
    run_config: RunConfig,
) -> dict[str, Any]:
    if run_config.sample_size is None:
        raise SystemExit("Experiment sample requested without a sample size.")

    sample_path = sample_cache_path(run_config.sample_size)
    regenerate = run_config.regenerate_sample
    sample_payload: dict[str, Any] | None = None

    if sample_path.exists() and not regenerate:
        candidate_payload = load_experiment_sample_payload(sample_path)
        if candidate_payload.get("normalized_sha256") == normalized_sha256:
            sample_payload = candidate_payload
            logger.info(
                "Reusing cached experiment sample from %s for %s prompts",
                sample_path,
                run_config.sample_size,
            )
        else:
            logger.warning(
                "Cached experiment sample %s does not match current normalized.jsonl SHA256; regenerating.",
                sample_path,
            )

    if sample_payload is None:
        sample_payload = generate_experiment_sample_payload(
            normalized_sha256=normalized_sha256,
            run_config=run_config,
        )
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        with sample_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(sample_payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        logger.info(
            "Wrote experiment sample with %s prompts to %s",
            len(sample_payload["prompt_ids"]),
            sample_path,
        )

    return sample_payload


def count_staging_records(artifacts: RunArtifacts) -> int:
    if not artifacts.staging_path.exists():
        return 0
    count = 0
    with artifacts.staging_path.open("r", encoding="utf-8") as staging_file:
        for line in staging_file:
            if line.strip():
                count += 1
    return count


def load_checkpoint(artifacts: RunArtifacts) -> dict[str, Any] | None:
    if not artifacts.checkpoint_path.exists():
        return None
    with artifacts.checkpoint_path.open("r", encoding="utf-8") as checkpoint_file:
        payload = json.load(checkpoint_file)
    if not isinstance(payload, dict):
        raise SystemExit("Classification checkpoint is malformed.")
    return payload


def save_checkpoint(artifacts: RunArtifacts, payload: dict[str, Any]) -> None:
    artifacts.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with artifacts.checkpoint_path.open("w", encoding="utf-8", newline="\n") as checkpoint:
        json.dump(payload, checkpoint, indent=2, ensure_ascii=False)
        checkpoint.write("\n")


def remove_path_if_exists(file_path: Path) -> None:
    if file_path.exists():
        file_path.unlink()


def prepare_run_state(
    *,
    artifacts: RunArtifacts,
    run_config: RunConfig,
    total_records: int,
    normalized_sha256: str,
    taxonomy_sha256: str,
    restart: bool,
) -> dict[str, Any]:
    checkpoint = load_checkpoint(artifacts)

    if restart:
        remove_path_if_exists(artifacts.staging_path)
        remove_path_if_exists(artifacts.checkpoint_path)
        remove_path_if_exists(artifacts.failure_log_path)
        checkpoint = None

    model_name = MODEL_NAME
    if checkpoint is None:
        if artifacts.staging_path.exists():
            raise SystemExit(
                "Found classified_staging.jsonl without a matching checkpoint. "
                "Use --restart to discard stale staging state before classifying again."
            )
        remove_path_if_exists(artifacts.failure_log_path)
        return {
            "run_started_at": now_utc_iso(),
            "normalized_path": str(NORMALIZED_PATH),
            "proposed_taxonomy_path": str(PROPOSED_TAXONOMY_PATH),
            "classified_path": str(artifacts.classified_path),
            "classified_staging_path": str(artifacts.staging_path),
            "normalized_sha256": normalized_sha256,
            "taxonomy_sha256": taxonomy_sha256,
            "model": model_name,
            "batch_size": run_config.batch_size,
            "max_prompt_chars": run_config.max_prompt_chars,
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
    if checkpoint.get("model") != model_name:
        raise SystemExit(
            "Existing classification checkpoint does not match the current "
            "REDLIB_CLASSIFY_MODEL setting. Restart with --restart to begin a clean run."
        )

    staging_records = count_staging_records(artifacts)
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
    checkpoint["batch_size"] = run_config.batch_size
    checkpoint["max_prompt_chars"] = run_config.max_prompt_chars
    checkpoint["completed"] = False
    return checkpoint


def truncate_prompt(text: str, max_prompt_chars: int) -> str:
    if len(text) <= max_prompt_chars:
        return text
    truncated = text[: max_prompt_chars - 3].rstrip()
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
        "Allowed supporting traits (closed vocabulary, exact labels only): "
        + "; ".join(SUPPORTING_TRAIT_OPTIONS)
    )
    lines.append(
        f"Allowed fallback primary category when no approved category fits: {PRIMARY_FALLBACK_CATEGORY}"
    )
    return "\n".join(lines)


def build_batch_prompt(
    records: list[NormalizedRecord],
    taxonomy_reference: str,
    *,
    max_prompt_chars: int,
) -> str:
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
        lines.append(truncate_prompt(record.text, max_prompt_chars))
        lines.append("")
    return "\n".join(lines)


def estimate_request_input_tokens(
    client: Any,
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


def request_batch_classification_anthropic(
    *,
    client: Any,
    records: list[NormalizedRecord],
    taxonomy: dict[str, TaxonomyCategory],
    taxonomy_reference: str,
    checkpoint: dict[str, Any],
    artifacts: RunArtifacts,
    run_config: RunConfig,
) -> BatchRequestResult:
    if not records:
        raise ValueError("Cannot classify an empty batch.")

    model_name = MODEL_NAME
    user_prompt = build_batch_prompt(
        records,
        taxonomy_reference,
        max_prompt_chars=run_config.max_prompt_chars,
    )
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
            artifacts=artifacts,
            run_config=run_config,
        )
        right_result = request_batch_classification(
            client=client,
            records=records[midpoint:],
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            checkpoint=checkpoint,
            artifacts=artifacts,
            run_config=run_config,
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
            model_name,
            attempt_number,
            MAX_RETRIES_PER_BATCH,
            estimated_input_tokens if estimated_input_tokens is not None else "unknown",
        )
        try:
            response = client.messages.parse(
                model=model_name,
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
            logger.info(
                "Cache stats: creation=%s read=%s",
                getattr(response.usage, "cache_creation_input_tokens", 0),
                getattr(response.usage, "cache_read_input_tokens", 0),
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
                artifacts=artifacts,
                batch_prompt_ids=prompt_ids,
                response_stage="structured_output_validation_failure",
                error_message=str(error),
                response=locals().get("response"),
                estimated_input_tokens=estimated_input_tokens,
                model_name=model_name,
                extra_context={
                    "attempt_number": attempt_number,
                    "batch_size": len(records),
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                },
            )
            log_failure_event(
                artifacts,
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
                artifacts=artifacts,
                batch_prompt_ids=prompt_ids,
                response_stage="structured_output_request_failure",
                error_message=str(error),
                estimated_input_tokens=estimated_input_tokens,
                model_name=model_name,
                extra_context={
                    "attempt_number": attempt_number,
                    "batch_size": len(records),
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                },
            )
            log_failure_event(
                artifacts,
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
            artifacts=artifacts,
            run_config=run_config,
        )
        right_result = request_batch_classification(
            client=client,
            records=records[midpoint:],
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            checkpoint=checkpoint,
            artifacts=artifacts,
            run_config=run_config,
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
        artifacts,
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


def request_batch_classification(
    *,
    client: Any,
    records: list[NormalizedRecord],
    taxonomy: dict[str, TaxonomyCategory],
    taxonomy_reference: str,
    checkpoint: dict[str, Any],
    artifacts: RunArtifacts,
    run_config: RunConfig,
) -> BatchRequestResult:
    return request_batch_classification_anthropic(
        client=client,
        records=records,
        taxonomy=taxonomy,
        taxonomy_reference=taxonomy_reference,
        checkpoint=checkpoint,
        artifacts=artifacts,
        run_config=run_config,
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


def append_classified_records(artifacts: RunArtifacts, records: list[dict[str, Any]]) -> None:
    artifacts.staging_path.parent.mkdir(parents=True, exist_ok=True)
    with artifacts.staging_path.open("a", encoding="utf-8", newline="\n") as staging_file:
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


def build_experiment_summary(
    *,
    artifacts: RunArtifacts,
    run_config: RunConfig,
    result: dict[str, Any],
    runtime_seconds: float,
) -> dict[str, Any]:
    processed_records = safe_int(result.get("processed_records"), 0)
    token_usage = result.get("token_usage", {})
    total_input_tokens = safe_int(token_usage.get("actual_input_tokens"), 0)
    total_output_tokens = safe_int(token_usage.get("actual_output_tokens"), 0)
    prompts_per_second = (
        round(processed_records / runtime_seconds, 3) if runtime_seconds > 0 else 0.0
    )
    return {
        "experiment_name": run_config.experiment_name,
        "classified_path": str(artifacts.classified_path),
        "processed_records": processed_records,
        "total_records": safe_int(result.get("total_records"), 0),
        "limit": result.get("limit"),
        "batch_size": run_config.batch_size,
        "max_text_chars": run_config.max_prompt_chars,
        "retries": safe_int(result.get("batch_retry_attempts"), 0),
        "failure_events": safe_int(result.get("failure_events"), 0),
        "fallback_records": safe_int(result.get("records_classified_with_fallback"), 0),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "average_input_tokens_per_prompt": round(
            total_input_tokens / processed_records, 3
        )
        if processed_records
        else 0.0,
        "average_output_tokens_per_prompt": round(
            total_output_tokens / processed_records, 3
        )
        if processed_records
        else 0.0,
        "runtime_seconds": round(runtime_seconds, 3),
        "average_prompts_per_second": prompts_per_second,
        "normalized_sha256": result.get("normalized_sha256"),
        "estimated_cost_usd": token_usage.get("estimated_cost_usd"),
        "sample_size": result.get("sample_size"),
        "sample_prompt_ids_sha256": result.get("sample_prompt_ids_sha256"),
    }


def save_experiment_summary(artifacts: RunArtifacts, summary: dict[str, Any]) -> None:
    if artifacts.summary_path is None:
        return
    artifacts.summary_path.parent.mkdir(parents=True, exist_ok=True)
    with artifacts.summary_path.open("w", encoding="utf-8", newline="\n") as summary_file:
        json.dump(summary, summary_file, indent=2, ensure_ascii=False)
        summary_file.write("\n")


def load_classified_records_by_prompt_id(file_path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue
            payload = json.loads(stripped_line)
            if not isinstance(payload, dict):
                raise SystemExit(
                    f"Classified artifact {file_path} has non-object JSON at line {line_number}."
                )
            prompt_id = payload.get("prompt_id")
            if not isinstance(prompt_id, str) or not prompt_id:
                raise SystemExit(
                    f"Classified artifact {file_path} is missing prompt_id at line {line_number}."
                )
            records[prompt_id] = payload
    return records


def supporting_traits_match(left: list[str], right: list[str]) -> bool:
    return sorted(left) == sorted(right)


def compute_agreement_report(
    current_records: dict[str, dict[str, Any]],
    baseline_records: dict[str, dict[str, Any]],
    *,
    baseline_label: str,
) -> dict[str, Any]:
    common_prompt_ids = sorted(set(current_records).intersection(baseline_records))
    if not common_prompt_ids:
        raise SystemExit(
            f"No overlapping prompt_ids found when comparing experiment results against {baseline_label}."
        )

    primary_matches = 0
    subtechnique_matches = 0
    supporting_traits_matches = 0
    disagreements: list[dict[str, Any]] = []

    for prompt_id in common_prompt_ids:
        current_classification = current_records[prompt_id]["classification"]
        baseline_classification = baseline_records[prompt_id]["classification"]

        primary_equal = (
            current_classification.get("primary_category")
            == baseline_classification.get("primary_category")
        )
        subtechnique_equal = (
            current_classification.get("subtechnique")
            == baseline_classification.get("subtechnique")
        )
        current_traits = current_classification.get("supporting_traits", [])
        baseline_traits = baseline_classification.get("supporting_traits", [])
        supporting_traits_equal = (
            isinstance(current_traits, list)
            and isinstance(baseline_traits, list)
            and supporting_traits_match(current_traits, baseline_traits)
        )

        if primary_equal:
            primary_matches += 1
        if subtechnique_equal:
            subtechnique_matches += 1
        if supporting_traits_equal:
            supporting_traits_matches += 1

        if (
            not primary_equal
            or not subtechnique_equal
            or not supporting_traits_equal
        ) and len(disagreements) < 20:
            disagreements.append(
                {
                    "prompt_id": prompt_id,
                    "current": {
                        "primary_category": current_classification.get("primary_category"),
                        "subtechnique": current_classification.get("subtechnique"),
                        "supporting_traits": current_traits,
                    },
                    "baseline": {
                        "primary_category": baseline_classification.get("primary_category"),
                        "subtechnique": baseline_classification.get("subtechnique"),
                        "supporting_traits": baseline_traits,
                    },
                }
            )

    total = len(common_prompt_ids)
    return {
        "baseline_label": baseline_label,
        "compared_prompts": total,
        "primary_category_agreement": round(primary_matches / total * 100, 1),
        "subtechnique_agreement": round(subtechnique_matches / total * 100, 1),
        "supporting_traits_agreement": round(supporting_traits_matches / total * 100, 1),
        "disagreements": disagreements,
    }


def maybe_compute_experiment_agreement(
    *,
    artifacts: RunArtifacts,
    summary: dict[str, Any],
) -> dict[str, Any] | None:
    if artifacts.summary_path is None or artifacts.summary_path.parent.exists() is False:
        return None

    current_summary_path = artifacts.summary_path
    if not artifacts.classified_path.exists():
        return None

    candidate_summaries = sorted(artifacts.summary_path.parent.glob("*.summary.json"))
    matching_candidates: list[tuple[Path, dict[str, Any]]] = []
    for summary_path in candidate_summaries:
        if summary_path == current_summary_path:
            continue
        with summary_path.open("r", encoding="utf-8") as handle:
            candidate_summary = json.load(handle)
        if (
            candidate_summary.get("processed_records") == summary.get("processed_records")
            and candidate_summary.get("normalized_sha256") == summary.get("normalized_sha256")
            and candidate_summary.get("sample_prompt_ids_sha256")
            == summary.get("sample_prompt_ids_sha256")
        ):
            matching_candidates.append((summary_path, candidate_summary))

    if not matching_candidates:
        return None

    baseline_summary_path, baseline_summary = matching_candidates[0]
    baseline_classified_path = Path(str(baseline_summary["classified_path"]))
    if not baseline_classified_path.exists():
        logger.warning(
            "Skipping agreement report because baseline experiment artifact is missing: %s",
            baseline_classified_path,
        )
        return None

    current_records = load_classified_records_by_prompt_id(artifacts.classified_path)
    baseline_records = load_classified_records_by_prompt_id(baseline_classified_path)
    return compute_agreement_report(
        current_records,
        baseline_records,
        baseline_label=baseline_summary_path.stem,
    )


def log_experiment_summary(summary: dict[str, Any]) -> None:
    logger.info("Experiment Summary")
    logger.info("prompts processed: %s", summary["processed_records"])
    logger.info("retries: %s", summary["retries"])
    logger.info("failure_events: %s", summary["failure_events"])
    logger.info("fallback_records: %s", summary["fallback_records"])
    logger.info("total input tokens: %s", summary["total_input_tokens"])
    logger.info("total output tokens: %s", summary["total_output_tokens"])
    logger.info(
        "average input tokens per prompt: %s",
        summary["average_input_tokens_per_prompt"],
    )
    logger.info(
        "average output tokens per prompt: %s",
        summary["average_output_tokens_per_prompt"],
    )
    logger.info("runtime: %.3fs", summary["runtime_seconds"])
    logger.info(
        "average prompts/sec: %s",
        summary["average_prompts_per_second"],
    )
    logger.info(
        "estimated cost USD: %s",
        summary.get("estimated_cost_usd") or "not configured (set REDLIB_CLASSIFY_INPUT_COST_PER_MILLION_USD and REDLIB_CLASSIFY_OUTPUT_COST_PER_MILLION_USD)",
    )


def log_agreement_report(agreement_report: dict[str, Any]) -> None:
    logger.info("Agreement Report")
    logger.info("baseline: %s", agreement_report["baseline_label"])
    logger.info(
        "Primary category: %.1f%%",
        agreement_report["primary_category_agreement"],
    )
    logger.info(
        "Subtechnique: %.1f%%",
        agreement_report["subtechnique_agreement"],
    )
    logger.info(
        "Supporting traits: %.1f%%",
        agreement_report["supporting_traits_agreement"],
    )
    for disagreement in agreement_report["disagreements"]:
        logger.info(
            "Disagreement prompt_id=%s current=%s baseline=%s",
            disagreement["prompt_id"],
            disagreement["current"],
            disagreement["baseline"],
        )


def classify_corpus(
    *,
    limit: int | None,
    restart: bool,
    run_config: RunConfig,
) -> dict[str, Any]:
    if not NORMALIZED_PATH.exists():
        raise SystemExit(
            "Normalized corpus not found at data/corpus/normalized.jsonl. "
            "Run normalize_corpus.py before classify_corpus.py."
        )

    if run_config.sample_size is not None and limit is not None:
        raise SystemExit("--sample-size cannot be combined with --limit.")

    taxonomy, taxonomy_sha256 = load_taxonomy()
    normalized_sha256 = compute_file_sha256(NORMALIZED_PATH)
    total_records = count_normalized_records()
    sample_payload: dict[str, Any] | None = None
    prompt_id_filter: set[str] | None = None
    sample_prompt_ids_sha256: str | None = None
    if run_config.sample_size is not None:
        sample_payload = load_or_create_experiment_sample(
            normalized_sha256=normalized_sha256,
            run_config=run_config,
        )
        prompt_ids = sample_payload["prompt_ids"]
        prompt_id_filter = set(prompt_ids)
        sample_prompt_ids_sha256 = sample_prompt_ids_digest(prompt_ids)
        effective_total_records = len(prompt_ids)
    else:
        effective_total_records = (
            min(total_records, limit) if limit is not None else total_records
        )

    artifacts = build_run_artifacts(limit=limit, run_config=run_config)
    artifacts.classified_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = prepare_run_state(
        artifacts=artifacts,
        run_config=run_config,
        total_records=effective_total_records,
        normalized_sha256=normalized_sha256,
        taxonomy_sha256=taxonomy_sha256,
        restart=restart,
    )
    taxonomy_reference = build_taxonomy_reference(taxonomy)
    client = get_client()

    processed_records = safe_int(checkpoint.get("processed_records"), 0)
    if processed_records > effective_total_records:
        raise SystemExit(
            "Checkpoint processed_records exceeds the requested run limit. "
            "Restart with --restart or increase the limit."
        )

    batch_buffer: list[NormalizedRecord] = []
    batch_counter = safe_int(checkpoint.get("batches_completed"), 0)

    logger.info(
        "Starting classification run over %s normalized records using %s taxonomy categories with model=%s; resuming at record %s",
        effective_total_records,
        len(taxonomy),
        MODEL_NAME,
        processed_records,
    )

    for record in iter_normalized_records(
        start_index=processed_records,
        limit=None if limit is None else effective_total_records - processed_records,
        prompt_id_filter=prompt_id_filter,
    ):
        batch_buffer.append(record)
        if len(batch_buffer) < run_config.batch_size:
            continue

        batch_counter += 1
        batch_result = request_batch_classification(
            client=client,
            records=batch_buffer,
            taxonomy=taxonomy,
            taxonomy_reference=taxonomy_reference,
            checkpoint=checkpoint,
            artifacts=artifacts,
            run_config=run_config,
        )
        output_records = [
            build_output_record(record, batch_result.classifications[record.prompt_id])
            for record in batch_buffer
        ]
        append_classified_records(artifacts, output_records)

        processed_records += len(batch_buffer)
        checkpoint["processed_records"] = processed_records
        checkpoint["batches_completed"] = batch_counter
        checkpoint["last_updated_at"] = now_utc_iso()
        update_checkpoint_usage(checkpoint, batch_result)

        if batch_counter % CHECKPOINT_EVERY_BATCHES == 0:
            save_checkpoint(artifacts, checkpoint)

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
            artifacts=artifacts,
            run_config=run_config,
        )
        output_records = [
            build_output_record(record, batch_result.classifications[record.prompt_id])
            for record in batch_buffer
        ]
        append_classified_records(artifacts, output_records)

        processed_records += len(batch_buffer)
        checkpoint["processed_records"] = processed_records
        checkpoint["batches_completed"] = batch_counter
        checkpoint["last_updated_at"] = now_utc_iso()
        update_checkpoint_usage(checkpoint, batch_result)
        save_checkpoint(artifacts, checkpoint)

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

    if run_config.is_experiment:
        artifacts.staging_path.replace(artifacts.classified_path)
    elif limit is None:
        artifacts.staging_path.replace(artifacts.classified_path)
    else:
        logger.info(
            "Dry-run limit active; leaving partial results in staging file %s and not replacing %s",
            artifacts.staging_path,
            artifacts.classified_path,
        )

    checkpoint["completed"] = True
    checkpoint["last_updated_at"] = now_utc_iso()
    save_checkpoint(artifacts, checkpoint)

    return {
        "classified_path": str(artifacts.classified_path),
        "classified_staging_path": str(artifacts.staging_path),
        "processed_records": processed_records,
        "total_records": effective_total_records,
        "token_usage": checkpoint["token_usage"],
        "batch_retry_attempts": checkpoint["batch_retry_attempts"],
        "batches_split_for_token_pressure": checkpoint["batches_split_for_token_pressure"],
        "records_classified_with_fallback": checkpoint["records_classified_with_fallback"],
        "failure_events": checkpoint["failure_events"],
        "limit": limit,
        "normalized_sha256": normalized_sha256,
        "sample_size": run_config.sample_size,
        "sample_prompt_ids_sha256": sample_prompt_ids_sha256,
        "run_config": run_config,
        "artifacts": artifacts,
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
    parser.add_argument(
        "--experiment-name",
        type=str,
        default=None,
        help="Run in isolated experiment mode with experiment-scoped artifacts.",
    )
    parser.add_argument(
        "--max-text-chars",
        type=int,
        default=MAX_PROMPT_CHARS,
        help="Override prompt text truncation length for experiment runs.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help="Override batch size for experiment runs.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Run an experiment against a deterministic stratified sample of N prompts.",
    )
    parser.add_argument(
        "--min-per-source",
        type=int,
        default=40,
        help="Minimum per-source sample floor for sampled experiment runs.",
    )
    parser.add_argument(
        "--max-source-share",
        type=float,
        default=0.4,
        help="Maximum share any one source may occupy in a sampled experiment run.",
    )
    parser.add_argument(
        "--regenerate-sample",
        action="store_true",
        help="Regenerate the cached sampled experiment prompt set even if one already exists.",
    )
    args = parser.parse_args()
    if args.max_text_chars <= 0:
        raise SystemExit("--max-text-chars must be a positive integer.")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be a positive integer.")
    if args.sample_size is not None and args.sample_size <= 0:
        raise SystemExit("--sample-size must be a positive integer.")
    if args.min_per_source <= 0:
        raise SystemExit("--min-per-source must be a positive integer.")
    if args.max_source_share <= 0 or args.max_source_share > 1:
        raise SystemExit("--max-source-share must be greater than 0 and at most 1.")
    if args.sample_size is not None and args.limit is not None:
        raise SystemExit("--sample-size cannot be combined with --limit.")
    if (
        args.experiment_name is None
        and (
            args.max_text_chars != MAX_PROMPT_CHARS
            or args.batch_size != BATCH_SIZE
            or args.sample_size is not None
            or args.min_per_source != 40
            or args.max_source_share != 0.4
            or args.regenerate_sample
        )
    ):
        raise SystemExit(
            "--max-text-chars, --batch-size, --sample-size, "
            "--min-per-source, --max-source-share, and --regenerate-sample "
            "are experiment-only overrides. Provide --experiment-name to use them."
        )
    return args


def main() -> int:
    configure_logging()
    args = parse_args()
    run_config = RunConfig(
        batch_size=args.batch_size,
        max_prompt_chars=args.max_text_chars,
        experiment_name=args.experiment_name,
        sample_size=args.sample_size,
        min_per_source=args.min_per_source,
        max_source_share=args.max_source_share,
        regenerate_sample=args.regenerate_sample,
    )
    started_at = time.perf_counter()
    result = classify_corpus(
        limit=args.limit,
        restart=args.restart,
        run_config=run_config,
    )
    runtime_seconds = time.perf_counter() - started_at
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
    if run_config.is_experiment:
        artifacts: RunArtifacts = result["artifacts"]
        summary = build_experiment_summary(
            artifacts=artifacts,
            run_config=run_config,
            result=result,
            runtime_seconds=runtime_seconds,
        )
        save_experiment_summary(artifacts, summary)
        log_experiment_summary(summary)
        agreement_report = maybe_compute_experiment_agreement(
            artifacts=artifacts,
            summary=summary,
        )
        if agreement_report is not None:
            log_agreement_report(agreement_report)
    elif result["limit"] is None:
        logger.info("Final classified corpus written to %s", CLASSIFIED_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
