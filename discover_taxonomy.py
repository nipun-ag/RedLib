import hashlib
import json
import logging
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anthropic import Anthropic

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
MIN_SAMPLES_PER_SOURCE_PER_ROUND = 6
MAX_SAMPLES_PER_SOURCE_PER_ROUND = 18
SATURATION_STREAK_THRESHOLD = 2
MAX_EXCERPT_CHARS = 180
MAX_CITED_SAMPLE_IDS_PER_CATEGORY = 18
MAX_REPRESENTATIVE_EXCERPTS = 4
MAX_CATEGORY_COUNT = 16
JSON_REPAIR_ATTEMPTS = 2

REQUIRED_TAXONOMY_JSON_SHAPE = """{
  "round_summary": "short paragraph",
  "existing_category_matches": [
    {
      "name": "existing category name",
      "supporting_sample_ids": ["R01S001", "R02S004"],
      "refined_traits": ["trait", "trait"],
      "review_notes": "short note"
    }
  ],
  "new_candidate_categories": [
    {
      "name": "short label",
      "description": "1-3 sentence description",
      "distinguishing_traits": ["trait", "trait"],
      "supporting_sample_ids": ["R01S002", "R01S009"],
      "review_notes": "short note about overlap or ambiguity"
    }
  ],
  "open_questions": ["question", "question"]
}"""

SYSTEM_PROMPT = f"""You are helping propose a human-reviewed taxonomy for a jailbreak-prompt research corpus.

This is iterative taxonomy discovery, not final classification.

Your task:
- Review the excerpted prompts for this round.
- Compare them against any existing candidate categories already discovered.
- For each round sample, decide whether it strengthens an existing category or supports a genuinely new category.
- Focus on jailbreak mechanics and interaction patterns, not on the harmful topic domain.

Hard constraints:
- Do not reproduce full prompts.
- Do not invent numeric support counts.
- Do not cite any evidence except the provided sample IDs.
- Do not use source names, benchmark names, dataset names, or harm domains as taxonomy labels.
- Return valid JSON only, with no markdown fences and no surrounding commentary.

Return exactly this JSON shape:
{REQUIRED_TAXONOMY_JSON_SHAPE}

Rules:
- Propose only genuinely new categories in new_candidate_categories.
- Prefer broad recurring technique families over narrow one-off themes.
- If evidence is better explained by an existing category, use existing_category_matches instead of inventing a new one.
- If categories overlap, say so in review_notes.
"""

JSON_REPAIR_SYSTEM_PROMPT = f"""You repair malformed JSON responses.

Return only valid JSON with no markdown fences and no explanation.
Do not change the intended meaning unless a minimal structural fix is required.
Preserve category names, sample IDs, traits, descriptions, and review notes whenever possible.

The required JSON shape is:
{REQUIRED_TAXONOMY_JSON_SHAPE}
"""


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
    allocations = {
        source: min(available_by_source[source], MIN_SAMPLES_PER_SOURCE_PER_ROUND)
        for source in source_names
    }

    allocated_total = sum(allocations.values())
    if allocated_total > ROUND_SAMPLE_SIZE:
        base_allocation = max(1, ROUND_SAMPLE_SIZE // max(len(source_names), 1))
        allocations = {
            source: min(available_by_source[source], base_allocation)
            for source in source_names
        }

    remaining = ROUND_SAMPLE_SIZE - sum(allocations.values())
    while remaining > 0:
        progress_made = False
        source_priority = sorted(
            source_names,
            key=lambda source: (
                -(
                    min(available_by_source[source], MAX_SAMPLES_PER_SOURCE_PER_ROUND)
                    - allocations[source]
                ),
                source,
            ),
        )
        for source in source_priority:
            max_allowed = min(
                available_by_source[source], MAX_SAMPLES_PER_SOURCE_PER_ROUND
            )
            if allocations[source] >= max_allowed:
                continue
            allocations[source] += 1
            remaining -= 1
            progress_made = True
            if remaining == 0:
                break
        if not progress_made:
            break

    return allocations


def select_round_samples(
    records: list[NormalizedRecord],
    analyzed_prompt_ids: set[str],
    iteration_number: int,
) -> tuple[list[SampledRecord], dict[str, int], dict[str, int]]:
    remaining_records = [
        record for record in records if record.prompt_id not in analyzed_prompt_ids
    ]
    if not remaining_records:
        return [], {}, {}

    remaining_by_source: dict[str, list[NormalizedRecord]] = defaultdict(list)
    for record in remaining_records:
        remaining_by_source[record.source].append(record)

    available_by_source = {
        source: len(source_records)
        for source, source_records in sorted(remaining_by_source.items())
    }
    source_allocations = allocate_source_samples(available_by_source)
    effective_round_capacity = sum(
        min(count, MAX_SAMPLES_PER_SOURCE_PER_ROUND)
        for count in available_by_source.values()
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
        "Round %s requested up to %s samples and selected %s from %s unseen records across %s sources; per-source cap=%s, effective capped capacity=%s",
        iteration_number,
        ROUND_SAMPLE_SIZE,
        len(sampled_records),
        len(remaining_records),
        len(available_by_source),
        MAX_SAMPLES_PER_SOURCE_PER_ROUND,
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
    return samples, dict(sorted(round_source_counts.items())), dict(
        sorted(round_stratum_counts.items())
    )


def build_analysis_payload(
    samples: list[SampledRecord],
    source_counts: dict[str, int],
    existing_categories: list[dict[str, Any]],
) -> str:
    lines = [
        "Existing candidate categories before this round:",
    ]
    if existing_categories:
        for category in existing_categories:
            lines.append(
                f"- {category['name']}: {category['description']} | traits={', '.join(category['distinguishing_traits'][:4])}"
            )
    else:
        lines.append("- None yet. Propose initial categories from the evidence.")

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
    if not text_parts:
        raise ValueError("Anthropic response did not contain text content.")
    return "\n".join(text_parts).strip()


def extract_json_payload(response_text: str) -> dict[str, Any]:
    first_brace = response_text.find("{")
    last_brace = response_text.rfind("}")
    if first_brace == -1 or last_brace == -1 or last_brace < first_brace:
        raise ValueError("LLM response did not contain a JSON object.")

    payload_text = response_text[first_brace : last_brace + 1]
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"LLM returned invalid JSON: {error.msg}") from error

    if not isinstance(payload, dict):
        raise ValueError("LLM taxonomy response must be a JSON object.")
    return payload


def write_invalid_response_debug(
    *,
    iteration_number: int,
    response_stage: str,
    response_text: str,
    errors: list[str],
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
        "errors": errors,
        "raw_response": response_text,
    }
    with debug_path.open("w", encoding="utf-8", newline="\n") as debug_file:
        json.dump(payload, debug_file, indent=2, ensure_ascii=False)
        debug_file.write("\n")
    return debug_path


def request_json_repair(
    client: Anthropic,
    *,
    iteration_number: int,
    invalid_response: str,
    parse_error: str,
    repair_attempt: int,
) -> str:
    logger.info(
        "Requesting JSON repair attempt %s for taxonomy discovery round %s",
        repair_attempt,
        iteration_number,
    )
    repair_prompt = (
        f"Repair the malformed JSON for taxonomy discovery round {iteration_number}.\n\n"
        f"Parse error:\n{parse_error}\n\n"
        "Return only valid JSON matching the required schema.\n\n"
        "Malformed response:\n"
        f"{invalid_response}"
    )
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=4000,
        temperature=0,
        system=JSON_REPAIR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": repair_prompt}],
    )
    return extract_text_content(response)


def parse_llm_payload_with_repair(
    client: Anthropic,
    *,
    iteration_number: int,
    response_text: str,
) -> dict[str, Any]:
    errors: list[str] = []
    current_response_text = response_text

    for attempt_number in range(0, JSON_REPAIR_ATTEMPTS + 1):
        try:
            return extract_json_payload(current_response_text)
        except ValueError as error:
            error_message = str(error)
            errors.append(error_message)
            if attempt_number == 0:
                logger.warning(
                    "Taxonomy discovery round %s returned malformed JSON: %s",
                    iteration_number,
                    error_message,
                )
            else:
                logger.warning(
                    "Taxonomy discovery round %s JSON repair attempt %s failed: %s",
                    iteration_number,
                    attempt_number,
                    error_message,
                )

            if attempt_number >= JSON_REPAIR_ATTEMPTS:
                debug_path = write_invalid_response_debug(
                    iteration_number=iteration_number,
                    response_stage="invalid_json",
                    response_text=current_response_text,
                    errors=errors,
                )
                raise SystemExit(
                    "Taxonomy discovery could not recover valid JSON for "
                    f"round {iteration_number}. Saved debug response to {debug_path}."
                ) from error

            current_response_text = request_json_repair(
                client,
                iteration_number=iteration_number,
                invalid_response=current_response_text,
                parse_error=error_message,
                repair_attempt=attempt_number + 1,
            )

    raise AssertionError("JSON repair loop exited unexpectedly.")


def request_round_analysis(
    client: Anthropic,
    iteration_number: int,
    samples: list[SampledRecord],
    source_counts: dict[str, int],
    existing_categories: list[dict[str, Any]],
) -> dict[str, Any]:
    analysis_payload = build_analysis_payload(
        samples=samples,
        source_counts=source_counts,
        existing_categories=existing_categories,
    )
    user_prompt = (
        f"Analyze taxonomy discovery round {iteration_number}.\n\n"
        "Goals:\n"
        "- Strengthen existing categories when the evidence fits them.\n"
        "- Propose only genuinely new categories when the evidence does not fit existing ones.\n"
        "- Keep the taxonomy mechanism-focused, not topic-focused.\n\n"
        f"{analysis_payload}"
    )

    logger.info(
        "Requesting taxonomy discovery round %s from Anthropic model %s over %s sampled records",
        iteration_number,
        MODEL_NAME,
        len(samples),
    )
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=4000,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return parse_llm_payload_with_repair(
        client,
        iteration_number=iteration_number,
        response_text=extract_text_content(response),
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


def build_category_from_llm_family(
    family: dict[str, Any],
    sample_lookup: dict[str, SampledRecord],
) -> dict[str, Any] | None:
    name = ensure_string(family.get("name"))
    description = ensure_string(family.get("description"))
    review_notes = ensure_string(family.get("review_notes"))
    if not name or not description:
        return None

    supporting_sample_ids = family.get("supporting_sample_ids", [])
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

    prompt_ids = [sample_lookup[sample_id].prompt_id for sample_id in valid_sample_ids]
    source_distribution = Counter(
        sample_lookup[sample_id].source for sample_id in valid_sample_ids
    )
    representative_excerpts = [
        {
            "sample_id": sample_lookup[sample_id].sample_id,
            "prompt_id": sample_lookup[sample_id].prompt_id,
            "source": sample_lookup[sample_id].source,
            "source_file": sample_lookup[sample_id].source_file,
            "source_row": sample_lookup[sample_id].source_row,
            "excerpt": sample_lookup[sample_id].excerpt,
        }
        for sample_id in valid_sample_ids[:MAX_REPRESENTATIVE_EXCERPTS]
    ]

    return {
        "name": name,
        "description": description,
        "distinguishing_traits": normalize_trait_list(
            family.get("distinguishing_traits", [])
        ),
        "supporting_sample_ids": valid_sample_ids,
        "supporting_prompt_ids": prompt_ids,
        "support_count": len(valid_sample_ids),
        "source_distribution": dict(sorted(source_distribution.items())),
        "representative_excerpts": representative_excerpts,
        "review_notes": review_notes,
    }


def merge_existing_category_match(
    category: dict[str, Any],
    match_payload: dict[str, Any],
    sample_lookup: dict[str, SampledRecord],
) -> int:
    supporting_sample_ids = match_payload.get("supporting_sample_ids", [])
    if not isinstance(supporting_sample_ids, list):
        supporting_sample_ids = []

    valid_sample_ids = [
        sample_id
        for sample_id in supporting_sample_ids
        if isinstance(sample_id, str) and sample_id in sample_lookup
    ]
    if not valid_sample_ids:
        return 0

    before_count = len(category["supporting_sample_ids"])
    category["supporting_sample_ids"] = deduplicate_preserve_order(
        category["supporting_sample_ids"] + valid_sample_ids
    )[:MAX_CITED_SAMPLE_IDS_PER_CATEGORY]
    category["supporting_prompt_ids"] = [
        sample_lookup[sample_id].prompt_id
        for sample_id in category["supporting_sample_ids"]
    ]

    refined_traits = normalize_trait_list(match_payload.get("refined_traits", []))
    category["distinguishing_traits"] = deduplicate_preserve_order(
        category["distinguishing_traits"] + refined_traits
    )

    review_note = ensure_string(match_payload.get("review_notes"))
    if review_note:
        existing_notes = ensure_string(category.get("review_notes", ""))
        if existing_notes:
            category["review_notes"] = f"{existing_notes} | {review_note}"
        else:
            category["review_notes"] = review_note

    source_distribution = Counter(
        sample_lookup[sample_id].source for sample_id in category["supporting_sample_ids"]
    )
    category["support_count"] = len(category["supporting_sample_ids"])
    category["source_distribution"] = dict(sorted(source_distribution.items()))
    category["representative_excerpts"] = [
        {
            "sample_id": sample_lookup[sample_id].sample_id,
            "prompt_id": sample_lookup[sample_id].prompt_id,
            "source": sample_lookup[sample_id].source,
            "source_file": sample_lookup[sample_id].source_file,
            "source_row": sample_lookup[sample_id].source_row,
            "excerpt": sample_lookup[sample_id].excerpt,
        }
        for sample_id in category["supporting_sample_ids"][:MAX_REPRESENTATIVE_EXCERPTS]
    ]
    return max(len(category["supporting_sample_ids"]) - before_count, 0)


def build_existing_categories_payload(
    categories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "name": category["name"],
            "description": category["description"],
            "distinguishing_traits": category["distinguishing_traits"],
            "support_count": category["support_count"],
            "source_distribution": category["source_distribution"],
        }
        for category in categories
    ]


def run_iterative_discovery(records: list[NormalizedRecord]) -> dict[str, Any]:
    client = get_anthropic_client()
    analyzed_prompt_ids: set[str] = set()
    all_sample_lookup: dict[str, SampledRecord] = {}
    categories: list[dict[str, Any]] = []
    category_lookup: dict[str, dict[str, Any]] = {}
    iterations: list[dict[str, Any]] = []
    open_questions: list[str] = []
    no_new_category_streak = 0
    saturation_reason = "max_iterations_reached"

    total_source_counts = dict(
        sorted(Counter(record.source for record in records).items())
    )

    for iteration_number in range(1, MAX_ITERATIONS + 1):
        samples, source_counts, stratum_counts = select_round_samples(
            records=records,
            analyzed_prompt_ids=analyzed_prompt_ids,
            iteration_number=iteration_number,
        )
        if not samples:
            saturation_reason = "no_unseen_records_remaining"
            break

        existing_categories_before_round = len(categories)
        sample_lookup = {sample.sample_id: sample for sample in samples}
        all_sample_lookup.update(sample_lookup)
        analyzed_prompt_ids.update(sample.prompt_id for sample in samples)

        llm_payload = request_round_analysis(
            client=client,
            iteration_number=iteration_number,
            samples=samples,
            source_counts=source_counts,
            existing_categories=build_existing_categories_payload(categories),
        )

        round_summary = ensure_string(llm_payload.get("round_summary"))
        round_open_questions = llm_payload.get("open_questions", [])
        if isinstance(round_open_questions, list):
            open_questions.extend(
                question.strip()
                for question in round_open_questions
                if isinstance(question, str) and question.strip()
            )

        existing_matches = llm_payload.get("existing_category_matches", [])
        if not isinstance(existing_matches, list):
            existing_matches = []
        evidence_added_to_existing = 0
        matched_category_names = []
        for match in existing_matches:
            if not isinstance(match, dict):
                continue
            match_name = ensure_string(match.get("name"))
            if not match_name:
                continue
            category = category_lookup.get(canonical_category_key(match_name))
            if category is None:
                continue
            evidence_added_to_existing += merge_existing_category_match(
                category=category,
                match_payload=match,
                sample_lookup=all_sample_lookup,
            )
            matched_category_names.append(category["name"])

        new_candidate_payloads = llm_payload.get("new_candidate_categories", [])
        if not isinstance(new_candidate_payloads, list):
            new_candidate_payloads = []

        new_categories_added = []
        for family in new_candidate_payloads:
            if not isinstance(family, dict):
                continue
            category = build_category_from_llm_family(
                family=family,
                sample_lookup=sample_lookup,
            )
            if category is None:
                continue

            category_key = canonical_category_key(category["name"])
            if category_key in category_lookup:
                existing_category = category_lookup[category_key]
                merge_existing_category_match(
                    category=existing_category,
                    match_payload={
                        "supporting_sample_ids": category["supporting_sample_ids"],
                        "refined_traits": category["distinguishing_traits"],
                        "review_notes": category["review_notes"],
                    },
                    sample_lookup=all_sample_lookup,
                )
                continue

            categories.append(category)
            category_lookup[category_key] = category
            new_categories_added.append(category["name"])

        categories.sort(
            key=lambda category: (category["support_count"], category["name"].lower()),
            reverse=True,
        )
        categories = categories[:MAX_CATEGORY_COUNT]
        category_lookup = {
            canonical_category_key(category["name"]): category for category in categories
        }

        valid_new_category_count = len(new_categories_added)
        if valid_new_category_count == 0:
            no_new_category_streak += 1
        else:
            no_new_category_streak = 0

        iterations.append(
            {
                "iteration": iteration_number,
                "round_sample_count": len(samples),
                "cumulative_analyzed_sample_count": len(analyzed_prompt_ids),
                "round_source_counts": source_counts,
                "round_stratum_counts": stratum_counts,
                "existing_categories_before_round": existing_categories_before_round,
                "existing_category_matches": deduplicate_preserve_order(
                    matched_category_names
                ),
                "new_category_names": new_categories_added,
                "valid_new_category_count": valid_new_category_count,
                "evidence_added_to_existing_categories": evidence_added_to_existing,
                "round_summary": round_summary,
            }
        )

        logger.info(
            "Taxonomy discovery round %s analyzed %s records, added %s new categories, streak=%s",
            iteration_number,
            len(samples),
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
        "categories": categories,
        "iterations": iterations,
        "open_questions": deduplicate_preserve_order(open_questions),
        "analyzed_sample_count": len(analyzed_prompt_ids),
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
    if not discovery_result["categories"]:
        raise SystemExit(
            "Taxonomy discovery did not produce any validated proposed categories."
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "normalized_path": str(NORMALIZED_PATH),
        "proposed_taxonomy_path": str(PROPOSED_TAXONOMY_PATH),
        "report_version": 2,
        "human_review_required": True,
        "model": {
            "provider": "anthropic",
            "model": MODEL_NAME,
        },
        "sampling_strategy": {
            "seed": SAMPLING_SEED,
            "approach": (
                "deterministic, source-aware, stratified iterative sampling with "
                "stable prompt ordering and unseen-record rounds"
            ),
            "strata": ["source", "source_file", "prompt_length_bucket"],
            "round_sample_size": ROUND_SAMPLE_SIZE,
            "min_samples_per_source_per_round": MIN_SAMPLES_PER_SOURCE_PER_ROUND,
            "max_samples_per_source_per_round": MAX_SAMPLES_PER_SOURCE_PER_ROUND,
            "excerpt_max_chars": MAX_EXCERPT_CHARS,
        },
        "saturation_status": discovery_result["saturation_status"],
        "iterations": discovery_result["iterations"],
        "categories": discovery_result["categories"],
        "analyzed_sample_count": discovery_result["analyzed_sample_count"],
        "total_normalized_records": len(records),
        "source_record_counts": discovery_result["total_source_counts"],
        "analysis_constraints": {
            "normalized_data_modified": False,
            "classified_artifacts_created": False,
            "full_corpus_classification_performed": False,
            "qdrant_or_embedding_operations_performed": False,
            "numeric_support_counts_are_code_computed": True,
            "notes": [
                "The LLM proposes or refines category structure, but code controls sampling, iteration count, saturation detection, support counts, and source distribution.",
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
        "Wrote %s proposed taxonomy categories from %s analyzed samples over %s iterations to %s",
        len(report["categories"]),
        report["analyzed_sample_count"],
        report["saturation_status"]["completed_iterations"],
        PROPOSED_TAXONOMY_PATH,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
