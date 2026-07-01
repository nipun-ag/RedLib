import hashlib
import json
import logging
import math
import os
from collections import Counter, defaultdict
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
PROPOSED_TAXONOMY_STAGING_PATH = CORPUS_ROOT / "proposed_taxonomy_staging.json"
TAXONOMY_DEBUG_DIR = CORPUS_ROOT / "taxonomy_debug"

MODEL_NAME = os.environ.get("REDLIB_TAXONOMY_MODEL", "claude-haiku-4-5")
SAMPLING_SEED = "redlib-taxonomy-discovery-v2"
MAX_ITERATIONS = 4
ROUND_SAMPLE_SIZE = int(
    os.environ.get("REDLIB_TAXONOMY_SAMPLE_SIZE", "500")
)
ROUND_MAX_OUTPUT_TOKENS = int(
    os.environ.get("REDLIB_TAXONOMY_MAX_OUTPUT_TOKENS", "4000")
)
MIN_SAMPLES_PER_SOURCE_PER_ROUND = 6
MAX_SOURCE_SHARE_PER_ROUND = 0.35
SATURATION_STREAK_THRESHOLD = 2
MAX_EXCERPT_CHARS = 180
MAX_CITED_SAMPLE_IDS_PER_CATEGORY = 8
MAX_REPRESENTATIVE_EXCERPTS = 3
MAX_TOP_LEVEL_CATEGORY_COUNT = 8
MAX_CATEGORY_TRAITS = 6
MAX_SUBTECHNIQUES_PER_TOP_LEVEL = 5
MAX_EXISTING_TOP_LEVEL_MATCHES_PER_ROUND = 8
MAX_NEW_TOP_LEVEL_CATEGORIES_PER_ROUND = 2
MAX_OPEN_QUESTIONS = 3
PREFERRED_TOP_LEVEL_CATEGORIES = [
    "Instruction Override",
    "Persona / Character Adoption",
    "Authority or Legitimacy Spoofing",
    "Fictional / Hypothetical Framing",
    "Obfuscation / Encoding",
    "Legitimate Context or Research Framing",
    "Dual-Response / Response-Format Manipulation",
]

SYSTEM_PROMPT = """You are helping propose a human-reviewed taxonomy for a jailbreak-prompt research corpus.

This is iterative taxonomy discovery, not final classification.

Your task is intentionally narrow:
- Match round samples to existing top-level categories when they clearly fit.
- Propose genuinely new broad top-level mechanism families only when the current taxonomy does not fit.
- Place prompt variants and narrower jailbreak patterns under subtechniques, not as separate top-level categories.
- Use only the provided sample IDs as evidence.
- Keep outputs compact.

Hard constraints:
- Do not reproduce full prompts.
- Do not invent numeric support counts.
- Do not cite any evidence except the provided sample IDs.
- Do not use source names, benchmark names, dataset names, or harm domains as taxonomy labels.
- Do not return long summaries, paragraphs of commentary, or repeated rationale.
- Keep descriptions to one or two sentences.
- Keep traits short and discriminative.
- Top-level categories must be broad, durable jailbreak or red-team mechanisms.
- Low-support or one-off ideas should be demoted into subtechniques rather than introduced as new top-level categories.

Rules:
- Prefer broad recurring technique families over one-off themes.
- Prefer merging into these broad families when possible:
  Instruction Override
  Persona / Character Adoption
  Authority or Legitimacy Spoofing
  Fictional / Hypothetical Framing
  Obfuscation / Encoding
  Legitimate Context or Research Framing
  Dual-Response / Response-Format Manipulation
- Variants such as simulation, sandbox, alternate universe, DAN-style prompts, and hypothetical ethics suspension should usually be subtechniques under a broader family rather than new top-level categories.
- Cite only the strongest supporting sample IDs for each category.
- If evidence is better explained by an existing top-level category, strengthen that category instead of inventing a new one.
"""


class SubtechniqueOutput(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    supporting_sample_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_CITED_SAMPLE_IDS_PER_CATEGORY,
    )
    distinguishing_traits: list[str] = Field(
        default_factory=list,
        max_length=MAX_CATEGORY_TRAITS,
    )


class ExistingTopLevelCategoryMatchOutput(BaseModel):
    top_level_name: str = Field(min_length=1)
    supporting_sample_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_CITED_SAMPLE_IDS_PER_CATEGORY,
    )
    refined_traits: list[str] = Field(
        default_factory=list,
        max_length=MAX_CATEGORY_TRAITS,
    )
    subtechniques: list[SubtechniqueOutput] = Field(
        default_factory=list,
        max_length=MAX_SUBTECHNIQUES_PER_TOP_LEVEL,
    )


class NewTopLevelCategoryOutput(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    distinguishing_traits: list[str] = Field(
        default_factory=list,
        max_length=MAX_CATEGORY_TRAITS,
    )
    supporting_sample_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_CITED_SAMPLE_IDS_PER_CATEGORY,
    )
    subtechniques: list[SubtechniqueOutput] = Field(
        default_factory=list,
        max_length=MAX_SUBTECHNIQUES_PER_TOP_LEVEL,
    )


class RoundAnalysisOutput(BaseModel):
    existing_top_level_matches: list[ExistingTopLevelCategoryMatchOutput] = Field(
        default_factory=list,
        max_length=MAX_EXISTING_TOP_LEVEL_MATCHES_PER_ROUND,
    )
    new_top_level_categories: list[NewTopLevelCategoryOutput] = Field(
        default_factory=list,
        max_length=MAX_NEW_TOP_LEVEL_CATEGORIES_PER_ROUND,
    )
    open_questions: list[str] = Field(
        default_factory=list,
        max_length=MAX_OPEN_QUESTIONS,
    )


@dataclass(frozen=True)
class NormalizedRecord:
    prompt_id: str
    source: str
    source_file: str
    source_row: int
    text: str
    raw_fields: dict[str, Any]


@dataclass(frozen=True)
class SampledRecord:
    sample_id: str
    prompt_id: str
    source: str
    source_file: str
    source_row: int
    prompt_length_bucket: str
    excerpt: str
    stratification_signature: str


@dataclass(frozen=True)
class SampleSelectionResult:
    samples: list[SampledRecord]
    source_allocations: dict[str, int]
    source_counts: dict[str, int]
    stratum_counts: dict[str, int]
    requested_sample_size: int
    actual_sample_count: int
    effective_max_sample_count: int


@dataclass(frozen=True)
class RoundAnalysisResult:
    payload: RoundAnalysisOutput
    estimated_input_tokens: int | None
    actual_input_tokens: int
    actual_output_tokens: int
    stop_reason: str | None


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def build_excerpt(text: str, limit: int = MAX_EXCERPT_CHARS) -> str:
    collapsed = collapse_whitespace(text)
    if len(collapsed) <= limit:
        return collapsed
    truncated = collapsed[: limit - 3].rstrip()
    return f"{truncated}..."


def prompt_length_bucket(text: str) -> str:
    text_length = len(text)
    if text_length < 120:
        return "short"
    if text_length < 320:
        return "medium"
    if text_length < 700:
        return "long"
    return "very_long"


def load_normalized_records() -> list[NormalizedRecord]:
    if not NORMALIZED_PATH.exists():
        raise SystemExit(
            "Normalized corpus not found at data/corpus/normalized.jsonl. "
            "Run normalize_corpus.py before discover_taxonomy.py."
        )

    records: list[NormalizedRecord] = []
    with NORMALIZED_PATH.open("r", encoding="utf-8") as normalized_file:
        for line_number, line in enumerate(normalized_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as error:
                raise SystemExit(
                    f"Malformed normalized JSONL at line {line_number}: {error.msg}"
                ) from error

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

            records.append(
                NormalizedRecord(
                    prompt_id=prompt_id,
                    source=source,
                    source_file=source_file,
                    source_row=source_row,
                    text=text,
                    raw_fields=raw_fields,
                )
            )

    if not records:
        raise SystemExit("Normalized corpus is empty; cannot discover taxonomy.")

    return records


def build_stratum_key(record: NormalizedRecord) -> tuple[str, str, str]:
    return (record.source, record.source_file, prompt_length_bucket(record.text))


def stable_record_order(record: NormalizedRecord) -> str:
    return stable_hash(
        f"{SAMPLING_SEED}:{record.source}:{record.source_file}:{record.prompt_id}"
    )


def allocate_source_samples(
    available_by_source: dict[str, int],
) -> dict[str, int]:
    source_names = sorted(available_by_source)
    if not source_names or ROUND_SAMPLE_SIZE <= 0:
        return {}

    allocations = {source: 0 for source in source_names}
    remaining_budget = ROUND_SAMPLE_SIZE

    # Stage 1: guarantee a minimum contribution from every source when budget allows.
    guaranteed_total = sum(
        min(available_by_source[source], MIN_SAMPLES_PER_SOURCE_PER_ROUND)
        for source in source_names
    )
    if guaranteed_total <= ROUND_SAMPLE_SIZE:
        allocations = {
            source: min(available_by_source[source], MIN_SAMPLES_PER_SOURCE_PER_ROUND)
            for source in source_names
        }
        remaining_budget = ROUND_SAMPLE_SIZE - sum(allocations.values())
    else:
        while remaining_budget > 0:
            progress_made = False
            for source in source_names:
                if allocations[source] >= available_by_source[source]:
                    continue
                allocations[source] += 1
                remaining_budget -= 1
                progress_made = True
                if remaining_budget == 0:
                    break
            if not progress_made:
                break
        return allocations

    effective_max_source_share = max(
        MAX_SOURCE_SHARE_PER_ROUND,
        1 / max(len(source_names), 1),
    )
    max_source_allocation = math.ceil(ROUND_SAMPLE_SIZE * effective_max_source_share)
    per_source_caps = {
        source: min(
            available_by_source[source],
            max(max_source_allocation, allocations[source]),
        )
        for source in source_names
    }

    # Stage 2: allocate the remaining budget proportionally to the remaining
    # available records while enforcing an anti-dominance source cap.
    while remaining_budget > 0:
        eligible_sources = [
            source
            for source in source_names
            if allocations[source] < per_source_caps[source]
        ]
        if not eligible_sources:
            break

        remaining_records_by_source = {
            source: available_by_source[source] - allocations[source]
            for source in eligible_sources
        }
        total_remaining_records = sum(remaining_records_by_source.values())
        if total_remaining_records <= 0:
            break

        staged_additions = {source: 0 for source in eligible_sources}
        assigned_this_round = 0
        fractional_remainders: list[tuple[float, int, str]] = []

        for source in eligible_sources:
            capped_remaining = per_source_caps[source] - allocations[source]
            ideal_allocation = (
                remaining_budget
                * remaining_records_by_source[source]
                / total_remaining_records
            )
            staged_additions[source] = min(
                capped_remaining,
                math.floor(ideal_allocation),
            )
            assigned_this_round += staged_additions[source]
            fractional_remainders.append(
                (
                    ideal_allocation - math.floor(ideal_allocation),
                    remaining_records_by_source[source],
                    source,
                )
            )

        leftover_budget = remaining_budget - assigned_this_round
        for _, _, source in sorted(
            fractional_remainders,
            key=lambda item: (-item[0], -item[1], item[2]),
        ):
            if leftover_budget == 0:
                break
            capped_remaining = per_source_caps[source] - (
                allocations[source] + staged_additions[source]
            )
            if capped_remaining <= 0:
                continue
            staged_additions[source] += 1
            leftover_budget -= 1

        if all(addition == 0 for addition in staged_additions.values()):
            fallback_source = sorted(
                eligible_sources,
                key=lambda source: (-remaining_records_by_source[source], source),
            )[0]
            staged_additions[fallback_source] = 1

        for source, addition in staged_additions.items():
            allocations[source] += addition

        remaining_budget = ROUND_SAMPLE_SIZE - sum(allocations.values())

    return allocations


def select_round_samples(
    records: list[NormalizedRecord],
    analyzed_prompt_ids: set[str],
    iteration_number: int,
) -> SampleSelectionResult:
    remaining_records = [
        record for record in records if record.prompt_id not in analyzed_prompt_ids
    ]
    if not remaining_records:
        return SampleSelectionResult(
            samples=[],
            source_allocations={},
            source_counts={},
            stratum_counts={},
            requested_sample_size=ROUND_SAMPLE_SIZE,
            actual_sample_count=0,
            effective_max_sample_count=0,
        )

    remaining_by_source: dict[str, list[NormalizedRecord]] = defaultdict(list)
    for record in remaining_records:
        remaining_by_source[record.source].append(record)

    available_by_source = {
        source: len(source_records)
        for source, source_records in sorted(remaining_by_source.items())
    }
    source_allocations = allocate_source_samples(available_by_source)
    effective_round_capacity = sum(
        source_allocations.get(source, 0) for source in available_by_source
    )

    sampled_records: list[NormalizedRecord] = []
    round_source_counts: Counter[str] = Counter()
    round_stratum_counts: Counter[str] = Counter()

    for source in sorted(remaining_by_source):
        source_records = remaining_by_source[source]
        stratified_records: dict[tuple[str, str, str], list[NormalizedRecord]] = (
            defaultdict(list)
        )
        for record in source_records:
            stratified_records[build_stratum_key(record)].append(record)

        ordered_strata = sorted(
            stratified_records,
            key=lambda key: stable_hash(f"{SAMPLING_SEED}:stratum:{source}:{key}"),
        )
        stratum_queues = {
            key: sorted(
                stratified_records[key],
                key=stable_record_order,
            )
            for key in ordered_strata
        }
        stratum_indices = {key: 0 for key in ordered_strata}

        target_count = source_allocations.get(source, 0)
        while round_source_counts[source] < target_count:
            progress_made = False
            for key in ordered_strata:
                queue = stratum_queues[key]
                queue_index = stratum_indices[key]
                if queue_index >= len(queue):
                    continue

                record = queue[queue_index]
                stratum_indices[key] += 1
                sampled_records.append(record)
                round_source_counts[source] += 1
                round_stratum_counts["|".join(key)] += 1
                progress_made = True

                if round_source_counts[source] >= target_count:
                    break
            if not progress_made:
                break

    sampled_records = sampled_records[:ROUND_SAMPLE_SIZE]
    logger.info(
        "Round %s requested %s samples and selected %s from %s unseen records across %s sources; target allocations=%s; effective capacity=%s",
        iteration_number,
        ROUND_SAMPLE_SIZE,
        len(sampled_records),
        len(remaining_records),
        len(available_by_source),
        dict(sorted(source_allocations.items())),
        effective_round_capacity,
    )
    samples = [
        SampledRecord(
            sample_id=f"R{iteration_number:02d}S{index:03d}",
            prompt_id=record.prompt_id,
            source=record.source,
            source_file=record.source_file,
            source_row=record.source_row,
            prompt_length_bucket=prompt_length_bucket(record.text),
            excerpt=build_excerpt(record.text),
            stratification_signature="|".join(build_stratum_key(record)),
        )
        for index, record in enumerate(sampled_records, start=1)
    ]
    return SampleSelectionResult(
        samples=samples,
        source_allocations=dict(sorted(source_allocations.items())),
        source_counts=dict(sorted(round_source_counts.items())),
        stratum_counts=dict(sorted(round_stratum_counts.items())),
        requested_sample_size=ROUND_SAMPLE_SIZE,
        actual_sample_count=len(samples),
        effective_max_sample_count=effective_round_capacity,
    )


def build_analysis_payload(
    samples: list[SampledRecord],
    source_counts: dict[str, int],
    existing_categories: list[dict[str, Any]],
) -> str:
    lines = [
        "Existing top-level taxonomy categories before this round:",
    ]
    if existing_categories:
        for category in existing_categories:
            lines.append(
                f"- {category['name']}: {category['description']} | traits={', '.join(category['distinguishing_traits'][:4])}"
            )
            if category.get("subtechniques"):
                lines.append(
                    "  subtechniques: "
                    + ", ".join(
                        subtechnique["name"]
                        for subtechnique in category["subtechniques"][:MAX_SUBTECHNIQUES_PER_TOP_LEVEL]
                    )
                )
    else:
        lines.append(
            "- None yet. Propose initial broad top-level categories from the evidence."
        )

    lines.append("")
    lines.append(
        f"Return at most {MAX_NEW_TOP_LEVEL_CATEGORIES_PER_ROUND} new top-level categories, "
        f"at most {MAX_SUBTECHNIQUES_PER_TOP_LEVEL} subtechniques per top-level category, "
        f"at most {MAX_CITED_SAMPLE_IDS_PER_CATEGORY} supporting sample IDs per category or subtechnique, "
        f"and at most {MAX_OPEN_QUESTIONS} short open questions."
    )
    lines.append("Preferred broad top-level categories:")
    for category_name in PREFERRED_TOP_LEVEL_CATEGORIES:
        lines.append(f"- {category_name}")
    lines.append("")
    lines.append("Round sample distribution by source:")
    for source, count in source_counts.items():
        lines.append(f"- {source}: {count}")

    lines.append("")
    lines.append(
        "Excerpted round samples (sample_id | prompt_id | source | source_file:source_row | length_bucket | excerpt):"
    )
    for sample in samples:
        lines.append(
            f"{sample.sample_id} | {sample.prompt_id} | {sample.source} | "
            f"{sample.source_file}:{sample.source_row} | {sample.prompt_length_bucket} | {sample.excerpt}"
        )
    return "\n".join(lines)


def get_anthropic_client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Run with Doppler or export the key before discover_taxonomy.py."
        )
    return Anthropic(api_key=api_key)


def extract_text_content(response: Any) -> str:
    text_parts = []
    for block in response.content:
        block_text = getattr(block, "text", None)
        if block_text:
            text_parts.append(block_text)
    return "\n".join(text_parts).strip()


def write_structured_output_debug(
    *,
    iteration_number: int,
    response_stage: str,
    error_message: str,
    response: Any | None = None,
    estimated_input_tokens: int | None = None,
    extra_context: dict[str, Any] | None = None,
) -> Path:
    TAXONOMY_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    debug_path = (
        TAXONOMY_DEBUG_DIR
        / f"round_{iteration_number:02d}_{response_stage}_{timestamp}.json"
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration_number,
        "model": MODEL_NAME,
        "response_stage": response_stage,
        "error": error_message,
        "structured_output_enabled": True,
        "schema": "RoundAnalysisOutput",
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


def estimate_round_input_tokens(
    client: Anthropic,
    *,
    user_prompt: str,
) -> int | None:
    try:
        token_estimate = client.messages.count_tokens(
            model=MODEL_NAME,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            output_format=RoundAnalysisOutput,
        )
    except Exception as error:
        logger.warning("Could not estimate taxonomy round input tokens: %s", error)
        return None
    return token_estimate.input_tokens


def request_round_analysis(
    client: Anthropic,
    iteration_number: int,
    samples: list[SampledRecord],
    source_counts: dict[str, int],
    existing_categories: list[dict[str, Any]],
) -> RoundAnalysisResult:
    analysis_payload = build_analysis_payload(
        samples=samples,
        source_counts=source_counts,
        existing_categories=existing_categories,
    )
    user_prompt = (
        f"Analyze taxonomy discovery round {iteration_number}.\n\n"
        "Goals:\n"
        "- Strengthen existing top-level categories when the evidence fits them.\n"
        "- Propose only genuinely new top-level categories when the evidence does not fit existing ones.\n"
        "- Keep the taxonomy mechanism-focused, not topic-focused.\n"
        "- Keep the output compact and schema-compliant.\n\n"
        "If an idea is narrow, variant-like, or low support, place it under a "
        "broader top-level category as a subtechnique instead of creating a new "
        "top-level category.\n\n"
        f"{analysis_payload}"
    )
    estimated_input_tokens = estimate_round_input_tokens(
        client,
        user_prompt=user_prompt,
    )

    logger.info(
        "Requesting taxonomy discovery round %s from Anthropic model %s over %s sampled records with structured outputs (estimated input tokens=%s, max output tokens=%s)",
        iteration_number,
        MODEL_NAME,
        len(samples),
        estimated_input_tokens if estimated_input_tokens is not None else "unknown",
        ROUND_MAX_OUTPUT_TOKENS,
    )
    try:
        response = client.messages.parse(
            model=MODEL_NAME,
            max_tokens=ROUND_MAX_OUTPUT_TOKENS,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            output_format=RoundAnalysisOutput,
        )
    except (ValidationError, ValueError) as error:
        logger.error(
            "Structured taxonomy output failed validation in round %s. "
            "Likely cause: output truncation or structured-output validation failure. %s",
            iteration_number,
            error,
        )
        debug_path = write_structured_output_debug(
            iteration_number=iteration_number,
            response_stage="structured_output_validation_failure",
            error_message=(
                "Structured taxonomy output failed validation before a parsed "
                f"response was returned: {error}"
            ),
            estimated_input_tokens=estimated_input_tokens,
            extra_context={
                "likely_cause": (
                    "output_truncation_or_structured_output_validation_failure"
                ),
                "sample_count": len(samples),
                "source_counts": source_counts,
                "max_output_tokens": ROUND_MAX_OUTPUT_TOKENS,
                "exception_type": type(error).__name__,
            },
        )
        raise SystemExit(
            "Taxonomy discovery structured output failed validation for "
            f"round {iteration_number}. Likely cause: output truncation or "
            f"schema validation failure. Saved debug response to {debug_path}."
        ) from error
    except Exception as error:
        logger.error(
            "Structured taxonomy output request failed in round %s: %s",
            iteration_number,
            error,
        )
        debug_path = write_structured_output_debug(
            iteration_number=iteration_number,
            response_stage="structured_output_request_failure",
            error_message=f"Structured taxonomy request failed: {error}",
            estimated_input_tokens=estimated_input_tokens,
            extra_context={
                "sample_count": len(samples),
                "source_counts": source_counts,
                "max_output_tokens": ROUND_MAX_OUTPUT_TOKENS,
                "exception_type": type(error).__name__,
            },
        )
        raise SystemExit(
            "Taxonomy discovery request failed before a structured response "
            f"was parsed for round {iteration_number}. Saved debug response "
            f"to {debug_path}."
        ) from error
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        logger.error(
            "Structured taxonomy output was incomplete in round %s. "
            "Likely cause: output truncation. stop_reason=%s",
            iteration_number,
            response.stop_reason,
        )
        error_message = (
            "Structured taxonomy output was incomplete or missing. "
            f"stop_reason={response.stop_reason}"
        )
        debug_path = write_structured_output_debug(
            iteration_number=iteration_number,
            response_stage="structured_output_failure",
            error_message=error_message,
            response=response,
            estimated_input_tokens=estimated_input_tokens,
            extra_context={
                "likely_cause": "output_truncation_or_missing_structured_output",
                "sample_count": len(samples),
                "source_counts": source_counts,
                "max_output_tokens": ROUND_MAX_OUTPUT_TOKENS,
            },
        )
        raise SystemExit(
            "Taxonomy discovery did not receive a complete structured output for "
            f"round {iteration_number}. Saved debug response to {debug_path}."
        )

    return RoundAnalysisResult(
        payload=response.parsed_output,
        estimated_input_tokens=estimated_input_tokens,
        actual_input_tokens=response.usage.input_tokens,
        actual_output_tokens=response.usage.output_tokens,
        stop_reason=response.stop_reason,
    )


def deduplicate_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    ordered_items = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered_items.append(item)
    return ordered_items


def canonical_category_key(name: str) -> str:
    return " ".join(name.lower().split())


def normalize_trait_list(traits: Any) -> list[str]:
    if not isinstance(traits, list):
        return []
    normalized_traits = []
    for trait in traits:
        if not isinstance(trait, str):
            continue
        stripped_trait = trait.strip()
        if not stripped_trait:
            continue
        normalized_traits.append(stripped_trait)
    return deduplicate_preserve_order(normalized_traits)


def ensure_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def build_representative_excerpts(
    supporting_sample_ids: list[str],
    sample_lookup: dict[str, SampledRecord],
) -> list[dict[str, Any]]:
    return [
        {
            "sample_id": sample_lookup[sample_id].sample_id,
            "prompt_id": sample_lookup[sample_id].prompt_id,
            "source": sample_lookup[sample_id].source,
            "source_file": sample_lookup[sample_id].source_file,
            "source_row": sample_lookup[sample_id].source_row,
            "excerpt": sample_lookup[sample_id].excerpt,
        }
        for sample_id in supporting_sample_ids[:MAX_REPRESENTATIVE_EXCERPTS]
        if sample_id in sample_lookup
    ]


def build_support_fields(
    supporting_sample_ids: list[str],
    sample_lookup: dict[str, SampledRecord],
) -> dict[str, Any]:
    prompt_ids = [sample_lookup[sample_id].prompt_id for sample_id in supporting_sample_ids]
    source_distribution = Counter(
        sample_lookup[sample_id].source for sample_id in supporting_sample_ids
    )
    return {
        "supporting_sample_ids": supporting_sample_ids,
        "supporting_prompt_ids": prompt_ids,
        "support_count": len(supporting_sample_ids),
        "source_distribution": dict(sorted(source_distribution.items())),
        "representative_excerpts": build_representative_excerpts(
            supporting_sample_ids,
            sample_lookup,
        ),
    }


def build_subtechnique_from_llm_payload(
    payload: dict[str, Any],
    sample_lookup: dict[str, SampledRecord],
) -> dict[str, Any] | None:
    name = ensure_string(payload.get("name"))
    description = ensure_string(payload.get("description"))
    if not name or not description:
        return None

    supporting_sample_ids = payload.get("supporting_sample_ids", [])
    if not isinstance(supporting_sample_ids, list):
        return None

    valid_sample_ids = deduplicate_preserve_order(
        [
            sample_id
            for sample_id in supporting_sample_ids
            if isinstance(sample_id, str) and sample_id in sample_lookup
        ]
    )[:MAX_CITED_SAMPLE_IDS_PER_CATEGORY]
    if not valid_sample_ids:
        return None

    subtechnique = {
        "name": name,
        "description": description,
        "distinguishing_traits": normalize_trait_list(
            payload.get("distinguishing_traits", [])
        ),
    }
    subtechnique.update(build_support_fields(valid_sample_ids, sample_lookup))
    return subtechnique


def build_top_level_category_from_llm_payload(
    payload: dict[str, Any],
    sample_lookup: dict[str, SampledRecord],
) -> dict[str, Any] | None:
    name = ensure_string(payload.get("name"))
    description = ensure_string(payload.get("description"))
    if not name or not description:
        return None

    direct_supporting_sample_ids = payload.get("supporting_sample_ids", [])
    if not isinstance(direct_supporting_sample_ids, list):
        direct_supporting_sample_ids = []

    valid_direct_supporting_sample_ids = deduplicate_preserve_order(
        [
            sample_id
            for sample_id in direct_supporting_sample_ids
            if isinstance(sample_id, str) and sample_id in sample_lookup
        ]
    )[:MAX_CITED_SAMPLE_IDS_PER_CATEGORY]

    subtechnique_payloads = payload.get("subtechniques", [])
    if not isinstance(subtechnique_payloads, list):
        subtechnique_payloads = []

    subtechniques = [
        subtechnique
        for subtechnique in (
            build_subtechnique_from_llm_payload(subtechnique_payload, sample_lookup)
            for subtechnique_payload in subtechnique_payloads
            if isinstance(subtechnique_payload, dict)
        )
        if subtechnique is not None
    ][:MAX_SUBTECHNIQUES_PER_TOP_LEVEL]

    if not valid_direct_supporting_sample_ids and not subtechniques:
        return None

    category = {
        "name": name,
        "description": description,
        "distinguishing_traits": normalize_trait_list(
            payload.get("distinguishing_traits", [])
        ),
        "direct_supporting_sample_ids": valid_direct_supporting_sample_ids,
        "subtechniques": subtechniques,
    }
    refresh_top_level_category(category, sample_lookup)
    return category


def refresh_top_level_category(
    category: dict[str, Any],
    sample_lookup: dict[str, SampledRecord],
) -> None:
    aggregate_supporting_sample_ids = deduplicate_preserve_order(
        category.get("direct_supporting_sample_ids", [])
        + [
            sample_id
            for subtechnique in category.get("subtechniques", [])
            for sample_id in subtechnique.get("supporting_sample_ids", [])
        ]
    )[:MAX_CITED_SAMPLE_IDS_PER_CATEGORY]

    category.update(build_support_fields(aggregate_supporting_sample_ids, sample_lookup))
    category["subtechniques"] = sorted(
        category.get("subtechniques", []),
        key=lambda subtechnique: (
            subtechnique.get("support_count", 0),
            subtechnique.get("name", "").lower(),
        ),
        reverse=True,
    )[:MAX_SUBTECHNIQUES_PER_TOP_LEVEL]


def merge_subtechnique(
    existing_subtechnique: dict[str, Any],
    incoming_subtechnique: dict[str, Any],
    sample_lookup: dict[str, SampledRecord],
) -> None:
    existing_subtechnique["supporting_sample_ids"] = deduplicate_preserve_order(
        existing_subtechnique["supporting_sample_ids"]
        + incoming_subtechnique["supporting_sample_ids"]
    )[:MAX_CITED_SAMPLE_IDS_PER_CATEGORY]
    existing_subtechnique["distinguishing_traits"] = deduplicate_preserve_order(
        existing_subtechnique["distinguishing_traits"]
        + incoming_subtechnique["distinguishing_traits"]
    )
    existing_subtechnique.update(
        build_support_fields(existing_subtechnique["supporting_sample_ids"], sample_lookup)
    )


def merge_top_level_category_match(
    category: dict[str, Any],
    match_payload: dict[str, Any],
    sample_lookup: dict[str, SampledRecord],
) -> int:
    direct_supporting_sample_ids = match_payload.get("supporting_sample_ids", [])
    if not isinstance(direct_supporting_sample_ids, list):
        direct_supporting_sample_ids = []

    valid_direct_supporting_sample_ids = [
        sample_id
        for sample_id in direct_supporting_sample_ids
        if isinstance(sample_id, str) and sample_id in sample_lookup
    ]

    before_count = len(category.get("supporting_sample_ids", []))
    category["direct_supporting_sample_ids"] = deduplicate_preserve_order(
        category.get("direct_supporting_sample_ids", []) + valid_direct_supporting_sample_ids
    )[:MAX_CITED_SAMPLE_IDS_PER_CATEGORY]
    category["distinguishing_traits"] = deduplicate_preserve_order(
        category["distinguishing_traits"]
        + normalize_trait_list(match_payload.get("refined_traits", []))
    )

    subtechnique_payloads = match_payload.get("subtechniques", [])
    if not isinstance(subtechnique_payloads, list):
        subtechnique_payloads = []

    subtechnique_lookup = {
        canonical_category_key(subtechnique["name"]): subtechnique
        for subtechnique in category.get("subtechniques", [])
    }

    for subtechnique_payload in subtechnique_payloads:
        if not isinstance(subtechnique_payload, dict):
            continue
        subtechnique = build_subtechnique_from_llm_payload(
            subtechnique_payload,
            sample_lookup,
        )
        if subtechnique is None:
            continue
        subtechnique_key = canonical_category_key(subtechnique["name"])
        if subtechnique_key in subtechnique_lookup:
            merge_subtechnique(
                subtechnique_lookup[subtechnique_key],
                subtechnique,
                sample_lookup,
            )
            continue
        category.setdefault("subtechniques", []).append(subtechnique)
        subtechnique_lookup[subtechnique_key] = subtechnique

    refresh_top_level_category(category, sample_lookup)
    return max(len(category["supporting_sample_ids"]) - before_count, 0)


def build_existing_categories_payload(
    categories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "name": category["name"],
            "description": category["description"],
            "distinguishing_traits": category["distinguishing_traits"],
            "subtechniques": [
                {
                    "name": subtechnique["name"],
                    "description": subtechnique["description"],
                }
                for subtechnique in category.get("subtechniques", [])
            ],
        }
        for category in categories
    ]


def serialize_top_level_category(category: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": category["name"],
        "description": category["description"],
        "distinguishing_traits": category["distinguishing_traits"],
        "supporting_sample_ids": category["supporting_sample_ids"],
        "supporting_prompt_ids": category["supporting_prompt_ids"],
        "support_count": category["support_count"],
        "source_distribution": category["source_distribution"],
        "representative_excerpts": category["representative_excerpts"],
        "subtechniques": [
            {
                "name": subtechnique["name"],
                "description": subtechnique["description"],
                "distinguishing_traits": subtechnique["distinguishing_traits"],
                "supporting_sample_ids": subtechnique["supporting_sample_ids"],
                "supporting_prompt_ids": subtechnique["supporting_prompt_ids"],
                "support_count": subtechnique["support_count"],
                "source_distribution": subtechnique["source_distribution"],
                "representative_excerpts": subtechnique["representative_excerpts"],
            }
            for subtechnique in category.get("subtechniques", [])
        ],
    }


def run_iterative_discovery(records: list[NormalizedRecord]) -> dict[str, Any]:
    client = get_anthropic_client()
    analyzed_prompt_ids: set[str] = set()
    all_sample_lookup: dict[str, SampledRecord] = {}
    top_level_categories: list[dict[str, Any]] = []
    top_level_category_lookup: dict[str, dict[str, Any]] = {}
    iterations: list[dict[str, Any]] = []
    open_questions: list[str] = []
    no_new_category_streak = 0
    saturation_reason = "max_iterations_reached"

    total_source_counts = dict(
        sorted(Counter(record.source for record in records).items())
    )
    total_estimated_input_tokens = 0
    total_actual_input_tokens = 0
    total_actual_output_tokens = 0

    for iteration_number in range(1, MAX_ITERATIONS + 1):
        sample_selection = select_round_samples(
            records=records,
            analyzed_prompt_ids=analyzed_prompt_ids,
            iteration_number=iteration_number,
        )
        if not sample_selection.samples:
            saturation_reason = "no_unseen_records_remaining"
            break

        existing_categories_before_round = len(top_level_categories)
        sample_lookup = {
            sample.sample_id: sample for sample in sample_selection.samples
        }
        all_sample_lookup.update(sample_lookup)
        analyzed_prompt_ids.update(
            sample.prompt_id for sample in sample_selection.samples
        )

        round_analysis = request_round_analysis(
            client=client,
            iteration_number=iteration_number,
            samples=sample_selection.samples,
            source_counts=sample_selection.source_counts,
            existing_categories=build_existing_categories_payload(top_level_categories),
        )
        llm_payload = round_analysis.payload.model_dump()
        if round_analysis.estimated_input_tokens is not None:
            total_estimated_input_tokens += round_analysis.estimated_input_tokens
        total_actual_input_tokens += round_analysis.actual_input_tokens
        total_actual_output_tokens += round_analysis.actual_output_tokens

        round_open_questions = llm_payload.get("open_questions", [])
        if isinstance(round_open_questions, list):
            open_questions.extend(
                question.strip()
                for question in round_open_questions
                if isinstance(question, str) and question.strip()
            )

        existing_matches = llm_payload.get("existing_top_level_matches", [])
        if not isinstance(existing_matches, list):
            existing_matches = []
        evidence_added_to_existing = 0
        matched_category_names = []
        for match in existing_matches:
            if not isinstance(match, dict):
                continue
            match_name = ensure_string(match.get("top_level_name"))
            if not match_name:
                continue
            category = top_level_category_lookup.get(canonical_category_key(match_name))
            if category is None:
                continue
            evidence_added_to_existing += merge_top_level_category_match(
                category=category,
                match_payload=match,
                sample_lookup=all_sample_lookup,
            )
            matched_category_names.append(category["name"])

        new_candidate_payloads = llm_payload.get("new_top_level_categories", [])
        if not isinstance(new_candidate_payloads, list):
            new_candidate_payloads = []

        new_categories_added = []
        for top_level_payload in new_candidate_payloads:
            if not isinstance(top_level_payload, dict):
                continue
            category = build_top_level_category_from_llm_payload(
                payload=top_level_payload,
                sample_lookup=sample_lookup,
            )
            if category is None:
                continue

            category_key = canonical_category_key(category["name"])
            if category_key in top_level_category_lookup:
                existing_category = top_level_category_lookup[category_key]
                merge_top_level_category_match(
                    category=existing_category,
                    match_payload={
                        "supporting_sample_ids": category["supporting_sample_ids"],
                        "refined_traits": category["distinguishing_traits"],
                        "subtechniques": category["subtechniques"],
                    },
                    sample_lookup=all_sample_lookup,
                )
                continue

            top_level_categories.append(category)
            top_level_category_lookup[category_key] = category
            new_categories_added.append(category["name"])

        top_level_categories.sort(
            key=lambda category: (category["support_count"], category["name"].lower()),
            reverse=True,
        )
        top_level_categories = top_level_categories[:MAX_TOP_LEVEL_CATEGORY_COUNT]
        top_level_category_lookup = {
            canonical_category_key(category["name"]): category
            for category in top_level_categories
        }

        valid_new_category_count = len(new_categories_added)
        if valid_new_category_count == 0:
            no_new_category_streak += 1
        else:
            no_new_category_streak = 0

        iterations.append(
            {
                "iteration": iteration_number,
                "requested_round_sample_size": sample_selection.requested_sample_size,
                "round_sample_count": sample_selection.actual_sample_count,
                "cumulative_analyzed_sample_count": len(analyzed_prompt_ids),
                "target_source_allocations": sample_selection.source_allocations,
                "round_source_counts": sample_selection.source_counts,
                "round_stratum_counts": sample_selection.stratum_counts,
                "effective_max_sample_count": sample_selection.effective_max_sample_count,
                "existing_top_level_categories_before_round": existing_categories_before_round,
                "existing_top_level_matches": deduplicate_preserve_order(
                    matched_category_names
                ),
                "new_top_level_category_names": new_categories_added,
                "valid_new_top_level_category_count": valid_new_category_count,
                "evidence_added_to_existing_top_levels": evidence_added_to_existing,
                "llm_usage": {
                    "structured_output_enabled": True,
                    "schema": "RoundAnalysisOutput",
                    "estimated_input_tokens": round_analysis.estimated_input_tokens,
                    "actual_input_tokens": round_analysis.actual_input_tokens,
                    "actual_output_tokens": round_analysis.actual_output_tokens,
                    "stop_reason": round_analysis.stop_reason,
                },
            }
        )

        logger.info(
            "Taxonomy discovery round %s analyzed %s/%s requested samples, added %s new top-level categories, streak=%s",
            iteration_number,
            sample_selection.actual_sample_count,
            sample_selection.requested_sample_size,
            valid_new_category_count,
            no_new_category_streak,
        )

        if no_new_category_streak >= SATURATION_STREAK_THRESHOLD:
            saturation_reason = (
                "no_meaningful_new_categories_for_consecutive_rounds"
            )
            break
    else:
        saturation_reason = "max_iterations_reached"

    return {
        "top_level_categories": [
            serialize_top_level_category(category)
            for category in top_level_categories
        ],
        "iterations": iterations,
        "open_questions": deduplicate_preserve_order(open_questions),
        "analyzed_sample_count": len(analyzed_prompt_ids),
        "token_usage": {
            "structured_output_enabled": True,
            "schema": "RoundAnalysisOutput",
            "estimated_total_input_tokens": total_estimated_input_tokens
            if total_estimated_input_tokens > 0
            else None,
            "actual_total_input_tokens": total_actual_input_tokens,
            "actual_total_output_tokens": total_actual_output_tokens,
        },
        "saturation_status": {
            "reached": saturation_reason != "max_iterations_reached"
            or no_new_category_streak >= SATURATION_STREAK_THRESHOLD,
            "reason": saturation_reason,
            "completed_iterations": len(iterations),
            "max_iterations": MAX_ITERATIONS,
            "consecutive_no_new_category_rounds": no_new_category_streak,
            "threshold": SATURATION_STREAK_THRESHOLD,
        },
        "total_source_counts": total_source_counts,
    }


def discover_taxonomy() -> dict[str, Any]:
    records = load_normalized_records()
    discovery_result = run_iterative_discovery(records)
    if not discovery_result["top_level_categories"]:
        raise SystemExit(
            "Taxonomy discovery did not produce any validated proposed categories."
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "normalized_path": str(NORMALIZED_PATH),
        "proposed_taxonomy_path": str(PROPOSED_TAXONOMY_PATH),
        "report_version": 4,
        "human_review_required": True,
        "model": {
            "provider": "anthropic",
            "model": MODEL_NAME,
            "structured_output_enabled": True,
            "structured_output_schema": "RoundAnalysisOutput",
            "round_max_output_tokens": ROUND_MAX_OUTPUT_TOKENS,
        },
        "sampling_strategy": {
            "seed": SAMPLING_SEED,
            "approach": (
                "deterministic, source-aware, stratified iterative sampling with "
                "stable prompt ordering, minimum per-source coverage, "
                "proportional remainder allocation, and unseen-record rounds"
            ),
            "strata": ["source", "source_file", "prompt_length_bucket"],
            "round_sample_size": ROUND_SAMPLE_SIZE,
            "min_samples_per_source_per_round": MIN_SAMPLES_PER_SOURCE_PER_ROUND,
            "max_source_share_per_round": MAX_SOURCE_SHARE_PER_ROUND,
            "excerpt_max_chars": MAX_EXCERPT_CHARS,
        },
        "saturation_status": discovery_result["saturation_status"],
        "iterations": discovery_result["iterations"],
        "top_level_categories": discovery_result["top_level_categories"],
        "analyzed_sample_count": discovery_result["analyzed_sample_count"],
        "total_normalized_records": len(records),
        "source_record_counts": discovery_result["total_source_counts"],
        "token_usage": discovery_result["token_usage"],
        "llm_output_contract": {
            "schema_backed": True,
            "schema": "RoundAnalysisOutput",
            "llm_owned_fields": [
                "existing_top_level_matches.top_level_name",
                "existing_top_level_matches.supporting_sample_ids",
                "existing_top_level_matches.refined_traits",
                "existing_top_level_matches.subtechniques",
                "new_top_level_categories.name",
                "new_top_level_categories.description",
                "new_top_level_categories.distinguishing_traits",
                "new_top_level_categories.supporting_sample_ids",
                "new_top_level_categories.subtechniques",
                "open_questions",
            ],
            "taxonomy_shape": "hierarchical_top_level_categories_with_subtechniques",
            "removed_freeform_fields": ["round_summary", "review_notes"],
        },
        "analysis_constraints": {
            "normalized_data_modified": False,
            "classified_artifacts_created": False,
            "full_corpus_classification_performed": False,
            "qdrant_or_embedding_operations_performed": False,
            "numeric_support_counts_are_code_computed": True,
            "notes": [
                "The LLM proposes or refines category structure, but code controls sampling, iteration count, saturation detection, support counts, source distribution, representative excerpts, and provenance.",
                "Category support_count values are counts of cited sample IDs from analyzed rounds, not full-corpus classification counts.",
                "Representative excerpts are truncated to avoid full prompt reproduction during taxonomy proposal.",
            ],
        },
        "open_questions": discovery_result["open_questions"],
        "notes_for_human_review": [
            "Review whether proposed categories describe jailbreak mechanics rather than harm-topic domains.",
            "Check whether any proposed categories should be merged before approving an operational taxonomy.",
            "Treat support counts as evidence within the analyzed sample, not as final full-corpus prevalence estimates.",
            "Approve, rename, merge, or reject categories before any later corpus-wide classification stage.",
        ],
    }


def write_proposed_taxonomy(report: dict[str, Any]) -> None:
    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
    with PROPOSED_TAXONOMY_STAGING_PATH.open(
        "w", encoding="utf-8", newline="\n"
    ) as taxonomy_file:
        json.dump(report, taxonomy_file, indent=2, ensure_ascii=False)
        taxonomy_file.write("\n")
    PROPOSED_TAXONOMY_STAGING_PATH.replace(PROPOSED_TAXONOMY_PATH)


def main() -> int:
    configure_logging()
    report = discover_taxonomy()
    write_proposed_taxonomy(report)
    logger.info(
        "Wrote %s proposed top-level taxonomy categories from %s analyzed samples over %s iterations to %s",
        len(report["top_level_categories"]),
        report["analyzed_sample_count"],
        report["saturation_status"]["completed_iterations"],
        PROPOSED_TAXONOMY_PATH,
    )
    logger.info(
        "Structured outputs active=%s; requested round sample size=%s; total actual token usage input=%s output=%s",
        report["model"]["structured_output_enabled"],
        report["sampling_strategy"]["round_sample_size"],
        report["token_usage"]["actual_total_input_tokens"],
        report["token_usage"]["actual_total_output_tokens"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
