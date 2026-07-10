import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedRecord:
    prompt_id: str
    source: str
    source_file: str
    source_row: int
    text: str
    raw_fields: dict[str, Any]


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def prompt_length_bucket(text: str) -> str:
    text_length = len(text)
    if text_length < 120:
        return "short"
    if text_length < 320:
        return "medium"
    if text_length < 700:
        return "long"
    return "very_long"


def build_stratum_key(record: NormalizedRecord) -> tuple[str, str, str]:
    return (record.source, record.source_file, prompt_length_bucket(record.text))


def stable_record_order(record: NormalizedRecord, seed: str) -> str:
    return stable_hash(
        f"{seed}:{record.source}:{record.source_file}:{record.prompt_id}"
    )


def allocate_source_samples(
    available_by_source: dict[str, int],
    sample_size: int,
    min_per_source: int,
    max_source_share: float,
) -> dict[str, int]:
    source_names = sorted(available_by_source)
    if not source_names or sample_size <= 0:
        return {}

    allocations = {source: 0 for source in source_names}
    remaining_budget = sample_size

    guaranteed_total = sum(
        min(available_by_source[source], min_per_source) for source in source_names
    )
    if guaranteed_total <= sample_size:
        allocations = {
            source: min(available_by_source[source], min_per_source)
            for source in source_names
        }
        remaining_budget = sample_size - sum(allocations.values())
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
        max_source_share,
        1 / max(len(source_names), 1),
    )
    max_source_allocation = math.ceil(sample_size * effective_max_source_share)
    per_source_caps = {
        source: min(
            available_by_source[source],
            max(max_source_allocation, allocations[source]),
        )
        for source in source_names
    }

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

        remaining_budget = sample_size - sum(allocations.values())

    return allocations


def select_stratified_sample(
    records: list[NormalizedRecord],
    sample_size: int,
    min_per_source: int,
    max_source_share: float,
    seed: str,
) -> list[NormalizedRecord]:
    if sample_size <= 0 or not records:
        return []

    records_by_source: dict[str, list[NormalizedRecord]] = defaultdict(list)
    for record in records:
        records_by_source[record.source].append(record)

    available_by_source = {
        source: len(source_records)
        for source, source_records in sorted(records_by_source.items())
    }
    source_allocations = allocate_source_samples(
        available_by_source=available_by_source,
        sample_size=sample_size,
        min_per_source=min_per_source,
        max_source_share=max_source_share,
    )

    sampled_records: list[NormalizedRecord] = []
    for source in sorted(records_by_source):
        source_records = records_by_source[source]
        stratified_records: dict[tuple[str, str, str], list[NormalizedRecord]] = (
            defaultdict(list)
        )
        for record in source_records:
            stratified_records[build_stratum_key(record)].append(record)

        ordered_strata = sorted(
            stratified_records,
            key=lambda key: stable_hash(f"{seed}:stratum:{source}:{key}"),
        )
        stratum_queues = {
            key: sorted(
                stratified_records[key],
                key=lambda record: stable_record_order(record, seed),
            )
            for key in ordered_strata
        }
        stratum_indices = {key: 0 for key in ordered_strata}

        selected_for_source = 0
        target_count = source_allocations.get(source, 0)
        while selected_for_source < target_count:
            progress_made = False
            for key in ordered_strata:
                queue = stratum_queues[key]
                queue_index = stratum_indices[key]
                if queue_index >= len(queue):
                    continue

                sampled_records.append(queue[queue_index])
                stratum_indices[key] += 1
                selected_for_source += 1
                progress_made = True

                if selected_for_source >= target_count:
                    break
            if not progress_made:
                break

    return sampled_records[:sample_size]
