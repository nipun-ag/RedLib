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
TAXONOMY_CANDIDATES_PATH = CORPUS_ROOT / "taxonomy_candidates.json"
TAXONOMY_CANDIDATES_STAGING_PATH = CORPUS_ROOT / "taxonomy_candidates_staging.json"

MODEL_NAME = os.environ.get("REDLIB_TAXONOMY_MODEL", "claude-haiku-4-5")
SAMPLING_SEED = "redlib-taxonomy-discovery-v1"
MAX_TOTAL_SAMPLES = 120
MIN_SAMPLES_PER_SOURCE = 10
MAX_SAMPLES_PER_SOURCE = 24
MAX_EXCERPT_CHARS = 220
MAX_FAMILY_COUNT = 12
MAX_SUPPORT_IDS_PER_FAMILY = 12
MAX_REPRESENTATIVE_EXCERPTS = 3

SYSTEM_PROMPT = """You are helping design a human-reviewed taxonomy for a jailbreak-prompt research corpus.

Your job is to infer likely jailbreak technique families from short prompt excerpts.

Important constraints:
- This is taxonomy discovery, not final classification.
- Focus on jailbreak mechanics and interaction patterns, not on the harmful topic domain.
- Do not use source names, benchmark names, or dataset names as category labels.
- Do not reproduce full prompts.
- Use only the provided sample IDs as evidence.
- Return valid JSON only, with no markdown fences and no surrounding commentary.

Return this exact JSON shape:
{
  "analysis_summary": "short paragraph",
  "candidate_families": [
    {
      "name": "short label",
      "description": "1-3 sentence description",
      "distinguishing_traits": ["trait", "trait"],
      "supporting_sample_ids": ["S001", "S014"],
      "review_notes": "short note about ambiguity, overlap, or why human review matters"
    }
  ],
  "open_questions": ["question", "question"]
}

Rules for the candidate families:
- Propose between 5 and 12 families.
- Each family must cite at least 2 supporting sample IDs unless the evidence is genuinely sparse.
- Supporting sample IDs should reflect diverse sources when possible.
- Prefer broad recurring technique families over narrow one-off themes.
- If two families are easily confused, say so in review_notes.
"""


@dataclass(frozen=True)
class NormalizedRecord:
    prompt_id: str
    source: str
    source_file: str
    source_row: int
    text: str


@dataclass(frozen=True)
class SampledRecord:
    sample_id: str
    prompt_id: str
    source: str
    source_file: str
    source_row: int
    excerpt: str


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

            if not all(
                [
                    isinstance(prompt_id, str),
                    isinstance(source, str),
                    isinstance(source_file, str),
                    isinstance(source_row, int),
                    isinstance(text, str),
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
                )
            )

    if not records:
        raise SystemExit("Normalized corpus is empty; cannot discover taxonomy.")

    return records


def allocate_source_samples(
    grouped_records: dict[str, list[NormalizedRecord]],
) -> dict[str, int]:
    total_records = sum(len(records) for records in grouped_records.values())
    if total_records <= MAX_TOTAL_SAMPLES:
        return {
            source: min(len(records), MAX_SAMPLES_PER_SOURCE)
            for source, records in grouped_records.items()
        }

    source_names = sorted(grouped_records)
    allocations = {
        source: min(len(grouped_records[source]), MIN_SAMPLES_PER_SOURCE)
        for source in source_names
    }

    allocated_total = sum(allocations.values())
    if allocated_total > MAX_TOTAL_SAMPLES:
        base_allocation = max(1, MAX_TOTAL_SAMPLES // len(source_names))
        allocations = {
            source: min(len(grouped_records[source]), base_allocation)
            for source in source_names
        }

    remaining = MAX_TOTAL_SAMPLES - sum(allocations.values())
    while remaining > 0:
        progress_made = False
        source_priority = sorted(
            source_names,
            key=lambda source: (
                -(
                    min(len(grouped_records[source]), MAX_SAMPLES_PER_SOURCE)
                    - allocations[source]
                ),
                source,
            ),
        )
        for source in source_priority:
            max_allowed = min(len(grouped_records[source]), MAX_SAMPLES_PER_SOURCE)
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


def select_sampled_records(records: list[NormalizedRecord]) -> tuple[list[SampledRecord], dict[str, int], dict[str, int]]:
    grouped_records: dict[str, list[NormalizedRecord]] = defaultdict(list)
    for record in records:
        grouped_records[record.source].append(record)

    source_record_counts = {
        source: len(source_records)
        for source, source_records in sorted(grouped_records.items())
    }
    allocations = allocate_source_samples(grouped_records)

    sampled_by_source: dict[str, list[NormalizedRecord]] = {}
    for source, source_records in grouped_records.items():
        stable_order = sorted(
            source_records,
            key=lambda record: stable_hash(f"{SAMPLING_SEED}:{record.prompt_id}"),
        )
        sampled_by_source[source] = stable_order[: allocations[source]]

    sampled_records: list[NormalizedRecord] = []
    source_names = sorted(sampled_by_source)
    source_indices = {source: 0 for source in source_names}
    while True:
        progress_made = False
        for source in source_names:
            index = source_indices[source]
            source_records = sampled_by_source[source]
            if index >= len(source_records):
                continue
            sampled_records.append(source_records[index])
            source_indices[source] += 1
            progress_made = True
        if not progress_made:
            break

    source_sample_counts = {
        source: len(sampled_by_source[source]) for source in sorted(sampled_by_source)
    }
    samples = [
        SampledRecord(
            sample_id=f"S{index:03d}",
            prompt_id=record.prompt_id,
            source=record.source,
            source_file=record.source_file,
            source_row=record.source_row,
            excerpt=build_excerpt(record.text),
        )
        for index, record in enumerate(sampled_records, start=1)
    ]
    return samples, source_record_counts, source_sample_counts


def build_analysis_payload(
    sampled_records: list[SampledRecord],
    source_record_counts: dict[str, int],
    source_sample_counts: dict[str, int],
) -> str:
    lines = [
        "Corpus summary:",
        f"- Total normalized records: {sum(source_record_counts.values())}",
        f"- Total sources: {len(source_record_counts)}",
        "- Per-source record counts:",
    ]
    for source, count in source_record_counts.items():
        lines.append(f"  - {source}: {count}")

    lines.append("- Per-source sample counts:")
    for source, count in source_sample_counts.items():
        lines.append(f"  - {source}: {count}")

    lines.append("")
    lines.append(
        "Excerpted samples (sample_id | source | source_file:source_row | excerpt):"
    )
    for sample in sampled_records:
        lines.append(
            f"{sample.sample_id} | {sample.source} | {sample.source_file}:{sample.source_row} | {sample.excerpt}"
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

    candidate_json = response_text[first_brace : last_brace + 1]
    try:
        parsed = json.loads(candidate_json)
    except json.JSONDecodeError as error:
        raise ValueError(f"LLM returned invalid JSON: {error.msg}") from error

    if not isinstance(parsed, dict):
        raise ValueError("LLM taxonomy response must be a JSON object.")
    return parsed


def request_taxonomy_candidates(
    client: Anthropic,
    sampled_records: list[SampledRecord],
    source_record_counts: dict[str, int],
    source_sample_counts: dict[str, int],
) -> dict[str, Any]:
    analysis_payload = build_analysis_payload(
        sampled_records=sampled_records,
        source_record_counts=source_record_counts,
        source_sample_counts=source_sample_counts,
    )

    user_prompt = (
        "Analyze the excerpted normalized jailbreak prompts below and propose a "
        "human-review taxonomy candidate set.\n\n"
        "Discovery goals:\n"
        "- Identify recurring jailbreak technique families.\n"
        "- Balance dominant sources against smaller sources.\n"
        "- Prefer mechanism-level families over source-specific or harm-topic labels.\n"
        "- Treat this as a proposal for review, not a final taxonomy.\n\n"
        f"{analysis_payload}"
    )

    logger.info(
        "Requesting taxonomy discovery from Anthropic model %s over %s sampled records",
        MODEL_NAME,
        len(sampled_records),
    )
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=4000,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return extract_json_payload(extract_text_content(response))


def deduplicate_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    ordered_items = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered_items.append(item)
    return ordered_items


def build_candidate_families(
    llm_payload: dict[str, Any],
    sampled_records: list[SampledRecord],
) -> list[dict[str, Any]]:
    raw_families = llm_payload.get("candidate_families")
    if not isinstance(raw_families, list) or not raw_families:
        raise ValueError("LLM taxonomy payload did not include candidate_families.")

    sample_lookup = {sample.sample_id: sample for sample in sampled_records}
    processed_families = []

    for family in raw_families[:MAX_FAMILY_COUNT]:
        if not isinstance(family, dict):
            continue

        name = family.get("name")
        description = family.get("description")
        review_notes = family.get("review_notes", "")
        traits = family.get("distinguishing_traits", [])
        supporting_sample_ids = family.get("supporting_sample_ids", [])

        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(description, str) or not description.strip():
            continue
        if not isinstance(review_notes, str):
            review_notes = ""
        if not isinstance(traits, list):
            traits = []
        if not isinstance(supporting_sample_ids, list):
            supporting_sample_ids = []

        valid_sample_ids = deduplicate_preserve_order(
            [
                sample_id
                for sample_id in supporting_sample_ids
                if isinstance(sample_id, str) and sample_id in sample_lookup
            ]
        )[:MAX_SUPPORT_IDS_PER_FAMILY]
        if not valid_sample_ids:
            continue

        source_distribution = Counter(
            sample_lookup[sample_id].source for sample_id in valid_sample_ids
        )
        representative_excerpts = [
            {
                "sample_id": sample_lookup[sample_id].sample_id,
                "source": sample_lookup[sample_id].source,
                "source_file": sample_lookup[sample_id].source_file,
                "source_row": sample_lookup[sample_id].source_row,
                "excerpt": sample_lookup[sample_id].excerpt,
            }
            for sample_id in valid_sample_ids[:MAX_REPRESENTATIVE_EXCERPTS]
        ]

        processed_families.append(
            {
                "name": name.strip(),
                "description": description.strip(),
                "distinguishing_traits": [
                    trait.strip()
                    for trait in traits
                    if isinstance(trait, str) and trait.strip()
                ],
                "supporting_sample_ids": valid_sample_ids,
                "support_in_analyzed_sample": {
                    "record_count": len(valid_sample_ids),
                    "source_distribution": dict(sorted(source_distribution.items())),
                },
                "representative_excerpts": representative_excerpts,
                "review_notes": review_notes.strip(),
            }
        )

    processed_families.sort(
        key=lambda family: (
            family["support_in_analyzed_sample"]["record_count"],
            family["name"].lower(),
        ),
        reverse=True,
    )

    if not processed_families:
        raise ValueError("No valid taxonomy candidate families were produced.")

    return processed_families


def discover_taxonomy() -> dict[str, Any]:
    records = load_normalized_records()
    sampled_records, source_record_counts, source_sample_counts = select_sampled_records(
        records
    )
    client = get_anthropic_client()
    llm_payload = request_taxonomy_candidates(
        client=client,
        sampled_records=sampled_records,
        source_record_counts=source_record_counts,
        source_sample_counts=source_sample_counts,
    )
    candidate_families = build_candidate_families(
        llm_payload=llm_payload,
        sampled_records=sampled_records,
    )
    analysis_summary = llm_payload.get("analysis_summary", "")
    if not isinstance(analysis_summary, str):
        analysis_summary = ""

    open_questions = llm_payload.get("open_questions", [])
    if not isinstance(open_questions, list):
        open_questions = []

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "normalized_path": str(NORMALIZED_PATH),
        "taxonomy_candidates_path": str(TAXONOMY_CANDIDATES_PATH),
        "report_version": 1,
        "human_review_required": True,
        "model": {
            "provider": "anthropic",
            "model": MODEL_NAME,
        },
        "corpus_summary": {
            "total_records": len(records),
            "total_sources": len(source_record_counts),
            "source_record_counts": source_record_counts,
        },
        "sampling": {
            "strategy": (
                "deterministic source-aware stable-hash sampling with per-source "
                "minimums and caps"
            ),
            "seed": SAMPLING_SEED,
            "max_total_samples": MAX_TOTAL_SAMPLES,
            "min_samples_per_source": MIN_SAMPLES_PER_SOURCE,
            "max_samples_per_source": MAX_SAMPLES_PER_SOURCE,
            "analyzed_record_count": len(sampled_records),
            "source_sample_counts": source_sample_counts,
            "sampled_records": [
                {
                    "sample_id": sample.sample_id,
                    "prompt_id": sample.prompt_id,
                    "source": sample.source,
                    "source_file": sample.source_file,
                    "source_row": sample.source_row,
                    "excerpt": sample.excerpt,
                }
                for sample in sampled_records
            ],
        },
        "analysis_constraints": {
            "normalized_data_modified": False,
            "classified_artifacts_created": False,
            "full_corpus_classification_performed": False,
            "qdrant_or_embedding_operations_performed": False,
            "excerpt_max_chars": MAX_EXCERPT_CHARS,
            "notes": [
                "The LLM analyzes deterministic short excerpts rather than the full normalized corpus.",
                "Candidate families are proposals for human review and not final operational taxonomy labels.",
                "Support counts are counts within the analyzed sample based on cited sample IDs, not full-corpus classification totals.",
            ],
        },
        "analysis_summary": analysis_summary.strip(),
        "candidate_families": candidate_families,
        "open_questions": [
            question.strip()
            for question in open_questions
            if isinstance(question, str) and question.strip()
        ],
        "review_guidance": [
            "Review whether candidate families describe jailbreak mechanics rather than harm domains or dataset-specific artifacts.",
            "Check overlap between families before promoting them into an approved operational taxonomy.",
            "Revisit source/file prompt-field mappings if discovery suggests the corpus scope is too narrow or too broad for a source.",
        ],
    }


def write_taxonomy_candidates(report: dict[str, Any]) -> None:
    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
    with TAXONOMY_CANDIDATES_STAGING_PATH.open(
        "w", encoding="utf-8", newline="\n"
    ) as taxonomy_file:
        json.dump(report, taxonomy_file, indent=2, ensure_ascii=False)
        taxonomy_file.write("\n")
    TAXONOMY_CANDIDATES_STAGING_PATH.replace(TAXONOMY_CANDIDATES_PATH)


def main() -> int:
    configure_logging()
    report = discover_taxonomy()
    write_taxonomy_candidates(report)
    logger.info(
        "Wrote %s taxonomy candidate families from %s sampled records across %s sources to %s",
        len(report["candidate_families"]),
        report["sampling"]["analyzed_record_count"],
        report["corpus_summary"]["total_sources"],
        TAXONOMY_CANDIDATES_PATH,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
