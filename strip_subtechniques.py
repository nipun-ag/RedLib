import json
from pathlib import Path

CORPUS_ROOT = Path("data") / "corpus"
SOURCE_PATH = CORPUS_ROOT / "classified.jsonl"
OUTPUT_PATH = CORPUS_ROOT / "classified_clean.jsonl"
STAGING_PATH = CORPUS_ROOT / "classified_clean.staging.jsonl"
UNCLEAR_CATEGORY = "Unclear / Needs Review"


def strip_subtechniques() -> int:
    if not SOURCE_PATH.exists():
        raise SystemExit(
            "Classified corpus not found at data/corpus/classified.jsonl. "
            "Run classify_corpus.py before strip_subtechniques.py."
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if STAGING_PATH.exists():
        STAGING_PATH.unlink()

    total_records = 0
    stripped_non_none = 0
    stripped_none = 0
    unclear_records = 0

    with SOURCE_PATH.open("r", encoding="utf-8") as source_file, STAGING_PATH.open(
        "w", encoding="utf-8", newline="\n"
    ) as staging_file:
        for line_number, line in enumerate(source_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue

            try:
                record = json.loads(stripped_line)
            except json.JSONDecodeError as error:
                raise SystemExit(
                    f"Malformed classified JSONL at line {line_number}: {error.msg}"
                ) from error

            if not isinstance(record, dict):
                raise SystemExit(
                    f"Classified record at line {line_number} is not a JSON object."
                )

            classification = record.get("classification")
            if not isinstance(classification, dict):
                raise SystemExit(
                    f"Classified record at line {line_number} has invalid classification."
                )

            if "subtechnique" not in classification:
                raise SystemExit(
                    f"Classified record at line {line_number} is missing classification.subtechnique."
                )

            subtechnique = classification["subtechnique"]
            if subtechnique is None:
                stripped_none += 1
            else:
                stripped_non_none += 1

            if classification.get("primary_category") == UNCLEAR_CATEGORY:
                unclear_records += 1

            del classification["subtechnique"]

            json.dump(record, staging_file, ensure_ascii=False)
            staging_file.write("\n")
            total_records += 1

    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()
    STAGING_PATH.replace(OUTPUT_PATH)
    if STAGING_PATH.exists():
        STAGING_PATH.unlink()

    print(f"Total records processed: {total_records}")
    print(f"Records that had a non-None subtechnique (stripped): {stripped_non_none}")
    print(f"Records that had subtechnique=None (key removed): {stripped_none}")
    print(
        "Records where primary_category is 'Unclear / Needs Review': "
        f"{unclear_records}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(strip_subtechniques())
