import os
import logging
from datasets import load_dataset

logger = logging.getLogger(__name__)


def load_trustairlab() -> list[dict]:
    """Load TrustAIRLab jailbreak prompts from two configs."""
    prompts = []
    configs = ["jailbreak_2023_05_07", "jailbreak_2023_12_25"]
    hf_token = os.environ.get("HUGGINGFACE_TOKEN")

    for config in configs:
        try:
            dataset = load_dataset(
                "TrustAIRLab/in-the-wild-jailbreak-prompts",
                config,
                split="train",
                trust_remote_code=False,
                token=hf_token,
            )
            for row in dataset:
                prompts.append({"text": row["prompt"], "source": "trustairlab"})
            logger.info(
                f"Loaded TrustAIRLab config '{config}': {len(dataset)} prompts"
            )
        except Exception as e:
            logger.error(
                f"Failed to load TrustAIRLab config '{config}': {type(e).__name__}: {e}"
            )

    return prompts


def load_rubend18() -> list[dict]:
    """Load ChatGPT jailbreak prompts from rubend18."""
    prompts = []
    hf_token = os.environ.get("HUGGINGFACE_TOKEN")

    try:
        dataset = load_dataset(
            "rubend18/ChatGPT-Jailbreak-Prompts",
            split="train",
            trust_remote_code=False,
            token=hf_token,
        )
        for row in dataset:
            prompts.append({"text": row["Prompt"], "source": "rubend18"})
        logger.info(f"Loaded rubend18: {len(dataset)} prompts")
    except Exception as e:
        logger.error(f"Failed to load rubend18: {type(e).__name__}: {e}")

    return prompts


def load_jackhhao() -> list[dict]:
    """Load jailbreak-classification dataset, filtering for jailbreak type only."""
    prompts = []
    splits = ["train", "test"]
    hf_token = os.environ.get("HUGGINGFACE_TOKEN")

    for split in splits:
        try:
            dataset = load_dataset(
                "jackhhao/jailbreak-classification",
                split=split,
                trust_remote_code=False,
                token=hf_token,
            )
            # Filter to jailbreak type only
            filtered = [row for row in dataset if row["type"] == "jailbreak"]
            for row in filtered:
                prompts.append({"text": row["prompt"], "source": "jackhhao"})
            logger.info(
                f"Loaded jackhhao split '{split}': {len(filtered)} jailbreak prompts"
            )
        except Exception as e:
            logger.error(
                f"Failed to load jackhhao split '{split}': {type(e).__name__}: {e}"
            )

    return prompts


def load_harmbench() -> list[dict]:
    """Load HarmBench jailbreak behaviors from val and test splits."""
    prompts = []
    splits = ["val", "test"]
    hf_token = os.environ.get("HUGGINGFACE_TOKEN")

    for split in splits:
        try:
            dataset = load_dataset(
                "swiss-ai/harmbench",
                "HumanJailbreaks",
                split=split,
                trust_remote_code=False,
                token=hf_token,
            )
            for row in dataset:
                prompts.append({"text": row["Behavior"], "source": "harmbench"})
            logger.info(f"Loaded harmbench split '{split}': {len(dataset)} prompts")
        except Exception as e:
            logger.error(
                f"Failed to load harmbench split '{split}': {type(e).__name__}: {e}"
            )

    return prompts


def load_all_datasets() -> list[dict]:
    """Load all datasets, deduplicate on text field, return combined list."""
    all_prompts = []

    # Load each dataset
    trustairlab = load_trustairlab()
    all_prompts.extend(trustairlab)

    rubend18 = load_rubend18()
    all_prompts.extend(rubend18)

    jackhhao = load_jackhhao()
    all_prompts.extend(jackhhao)

    harmbench = load_harmbench()
    all_prompts.extend(harmbench)

    # Log counts by source
    logger.info(f"TrustAIRLab: {len(trustairlab)} prompts")
    logger.info(f"rubend18: {len(rubend18)} prompts")
    logger.info(f"jackhhao: {len(jackhhao)} prompts")
    logger.info(f"harmbench: {len(harmbench)} prompts")
    logger.info(f"Total before deduplication: {len(all_prompts)} prompts")

    # Deduplicate on 'text' field, keeping first occurrence
    seen = set()
    deduplicated = []
    for prompt_dict in all_prompts:
        text = prompt_dict["text"]
        if text not in seen:
            seen.add(text)
            deduplicated.append(prompt_dict)

    logger.info(f"Total after deduplication: {len(deduplicated)} prompts")

    return deduplicated
