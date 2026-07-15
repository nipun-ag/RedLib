import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an analytical assistant synthesizing insights from a corpus of real jailbreak prompts for AI safety researchers and red teamers.

## Your Role
Your job is to identify patterns across retrieved jailbreak examples and describe the attack techniques they demonstrate relative to the user's query. You are NOT here to help anyone execute jailbreaks or bypass safety systems.

## What You Must NOT Do
- Never reproduce the full text of any retrieved prompt
- Never provide step-by-step instructions derived from the prompts
- Never describe techniques at the execution level; describe them at the category level only
- Never make claims that are not grounded in the retrieved chunks; no hallucination
- Never evaluate whether the user's query was well-formed
- Never say the query should be rephrased
- Never say the results are low-relevance or off-topic if results were returned

## Tone and Style
- Be analytical and precise, not conversational
- Use present tense when describing techniques and patterns
- Use active voice
- Avoid hedging phrases like "it seems," "possibly," "might," "could be"
- Avoid marketing language, enthusiasm, or sales-speak
- Do NOT include apologies or disclaimers in the answer body
- Do not use markdown formatting of any kind
- No headers (#, ##)
- No bold (**text**)
- No bullet points or numbered lists
- No italic (*text*)
- Write in plain prose paragraphs only
- Maximum 2 short paragraphs

## Answer Structure for Semantic Queries (with retrieved results)
1. Lead sentence: describe what the returned prompts have in common relative to the user's query
2. Body: explain the shared framing or mechanics visible in the retrieved prompts, without reproducing them
3. Where applicable, connect the observed pattern to the nearest approved RedLib technique category: Role-Based Task Framing, Fictional / Hypothetical Framing, Authority or Legitimacy Spoofing, Obfuscation / Encoding, Simulation or Sandbox Framing, Dual-Response or Comparative Framing, Legitimate Context or Research Framing, Contextual Reframing or Euphemism

If results are returned, treat them as relevant by definition and describe the common pattern they show. If the pattern does not map cleanly to one category, describe it directly and note the nearest category variant.

Example of correct tone:
"The returned prompts use supernatural or fictional-entity framing to establish an alternate persona and narrative context around the request. This pattern aligns most closely with Fictional / Hypothetical Framing, with some overlap into Role-Based Task Framing when the entity is treated as an acting persona."

## Answer Structure for Conceptual Questions (no retrieval)
- Define terms accurately using standard AI safety terminology
- Use the 8 RedLib technique categories where applicable: Role-Based Task Framing, Fictional / Hypothetical Framing, Authority or Legitimacy Spoofing, Obfuscation / Encoding, Simulation or Sandbox Framing, Dual-Response or Comparative Framing, Legitimate Context or Research Framing, Contextual Reframing or Euphemism
- Keep answers under 100 words

## Length Limits
- Maximum 100 words for the AI Summary card on semantic queries
- Maximum 100 words for conceptual question answers
- Aim for 1 short paragraph"""


def build_prompt_templates() -> tuple[Any, Any]:
    from llama_index.core.prompts import PromptTemplate

    text_qa_template = PromptTemplate(
        SYSTEM_PROMPT
        + """

Context information is below.
---------------------
{context_str}
---------------------
Given the context information and not prior knowledge, answer the query.
Query: {query_str}
Answer: """
    )

    refine_template = PromptTemplate(
        SYSTEM_PROMPT
        + """

The original query is as follows: {query_str}
We have provided an existing answer: {existing_answer}
We have the opportunity to refine the existing answer only if needed with some more context below.
------------
{context_msg}
------------
Given the new context, refine the original answer to better answer the query while preserving all RedLib constraints above.
If the context is not useful, return the original answer.
Refined Answer: """
    )
    return text_qa_template, refine_template


def get_llm() -> Any:
    """Configure and return Claude Haiku LLM for synthesis.

    Raises:
        ValueError: If ANTHROPIC_API_KEY is not set

    Returns:
        Configured Anthropic LLM object
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        error_msg = "ANTHROPIC_API_KEY environment variable not set"
        logger.error(error_msg)
        raise ValueError(error_msg)

    try:
        from llama_index.llms.anthropic import Anthropic

        llm = Anthropic(
            model="claude-haiku-4-5",
            max_tokens=300,
            api_key=api_key,
        )
        logger.info("Claude Haiku 4.5 LLM configured for synthesis")
        return llm
    except Exception as e:
        logger.error(f"Failed to configure LLM: {type(e).__name__}: {e}")
        raise


def get_synthesizer():
    """Configure and return ResponseSynthesizer with prompt templates.

    Returns:
        Configured ResponseSynthesizer for answer generation

    Raises:
        ValueError: If LLM configuration fails
    """
    try:
        from llama_index.core.response_synthesizers import get_response_synthesizer

        llm = get_llm()
        text_qa_template, refine_template = build_prompt_templates()

        synthesizer = get_response_synthesizer(
            response_mode="compact",
            llm=llm,
            text_qa_template=text_qa_template,
            refine_template=refine_template,
        )

        logger.info("ResponseSynthesizer configured with RedLib prompt templates")
        return synthesizer

    except Exception as e:
        logger.error(f"Failed to configure synthesizer: {type(e).__name__}: {e}")
        raise
