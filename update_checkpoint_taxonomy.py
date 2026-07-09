import json
import hashlib
from pathlib import Path


CORPUS_ROOT = Path("data") / "corpus"
PROPOSED_TAXONOMY_PATH = CORPUS_ROOT / "proposed_taxonomy.json"
CLASSIFICATION_CHECKPOINT_PATH = CORPUS_ROOT / "classified_checkpoint.json"
CHECKPOINT_FIELD = "taxonomy_sha256"


def compute_file_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not PROPOSED_TAXONOMY_PATH.exists():
        raise SystemExit(
            f"Proposed taxonomy not found: {PROPOSED_TAXONOMY_PATH}"
        )
    if not CLASSIFICATION_CHECKPOINT_PATH.exists():
        raise SystemExit(
            f"Classification checkpoint not found: {CLASSIFICATION_CHECKPOINT_PATH}"
        )

    new_hash = compute_file_sha256(PROPOSED_TAXONOMY_PATH)

    with CLASSIFICATION_CHECKPOINT_PATH.open("r", encoding="utf-8") as handle:
        checkpoint = json.load(handle)

    if not isinstance(checkpoint, dict):
        raise SystemExit("Classification checkpoint is malformed.")
    if CHECKPOINT_FIELD not in checkpoint:
        raise SystemExit(
            f"Checkpoint field '{CHECKPOINT_FIELD}' not found in checkpoint."
        )

    old_hash = checkpoint.get(CHECKPOINT_FIELD)
    checkpoint[CHECKPOINT_FIELD] = new_hash

    with CLASSIFICATION_CHECKPOINT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(checkpoint, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(f"Old hash: {old_hash}")
    print(f"New hash: {new_hash}")
    print(f"Updated field: {CHECKPOINT_FIELD}")
    print(f"processed_records: {checkpoint.get('processed_records')}")


if __name__ == "__main__":
    main()
