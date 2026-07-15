# RedLib - Context

## Purpose of This File
This file documents how RedLib currently synthesizes answers after
retrieval. Read this before modifying `api/synthesizer.py`,
`api/router.py`, or the synthesis prompt used by the query pipeline.

---

## Current Synthesis Flow
RedLib uses one shared synthesis prompt for one corpus-grounded query path:

1. `api/router.py` builds a single `RetrieverQueryEngine` for all user
   queries.
2. `api/rag.py` initializes:
   - OpenAI embeddings via `text-embedding-3-small`
   - hybrid retrieval via `QueryFusionRetriever`
   - reranking via `CohereRerank`
   - synthesis via `get_response_synthesizer(response_mode="compact")`
   - a single corpus-backed query engine with no direct non-retrieval path
3. `api/synthesizer.py` uses Anthropic model `claude-haiku-4-5` with a
   single `SYSTEM_PROMPT`.
4. For both example-seeking and conceptual questions, the synthesizer
   receives reranked retrieved prompt nodes and produces a short
   grounded summary.

---

## What The Synthesizer Does
For all queries, Claude Haiku synthesizes a concise analytical summary
from retrieved prompt nodes.

The synthesizer does NOT:
- Explain how to execute jailbreaks
- Provide instructions for bypassing AI safety systems
- Reproduce full prompt text
- Fabricate claims that are not grounded in retrieved results

The synthesizer DOES:
- Identify patterns across retrieved prompts
- Name relevant RedLib technique categories
- Describe shared mechanics at the category level
- Note dataset distribution or confidence signals when useful
- Connect observed prompt patterns to the nearest approved RedLib category when applicable
- Treat returned results as relevant and describe the common pattern they show

---

## Audience
Users are AI safety practitioners, red teamers, researchers, and
security professionals who have already passed the responsible-use gate.
Assume technical literacy.

The retrieved corpus is scoped to adversarial jailbreak prompts that
attempt to manipulate, override, or bypass LLM safety behavior. Pure
harmful requests without a jailbreak mechanism are out of scope for the
corpus and should not be described as if they define RedLib's taxonomy.

---

## Tone and Style Rules
These rules are implemented directly in `api/synthesizer.py`:

- Analytical and precise, not conversational
- Present tense when describing techniques and patterns
- Active voice
- No hedging phrases such as "it seems," "possibly," "might," or "could be"
- No marketing language, enthusiasm, or sales tone
- No apologies or disclaimer language in the answer body
- Keep answers under 100 words
- Prefer one short analytical paragraph

---

## Semantic Query Structure
The current system prompt instructs Haiku to answer corpus-grounded queries in
this structure:

1. Lead sentence describing what the returned prompts have in common relative to the user's query
2. Body describing the shared framing or mechanics visible in the retrieved prompts
3. Where supported, a connection to the nearest approved RedLib technique category

The answer should describe technique mechanics at the category level and
must not reproduce the prompts themselves.

Example of correct tone:
"The returned prompts use supernatural or fictional-entity framing to
establish an alternate persona and narrative context. This pattern maps
most closely to Fictional / Hypothetical Framing, with some overlap into
Role-Based Task Framing when the entity is treated as an acting persona."

Example of incorrect tone:
"Great question. These prompts are really creative and could be useful
for future red teaming."

---

## Hard Constraints In The Live Prompt
The current `SYSTEM_PROMPT` explicitly enforces these constraints:

1. Never reproduce the full text of any retrieved prompt
2. Never provide step-by-step instructions derived from the prompts
3. Never describe techniques at the execution level
4. Never evaluate query quality or suggest rephrasing
5. Ground every claim in retrieved results
6. Treat returned results as relevant and describe their shared pattern
7. Keep semantic-query answers under 100 words
8. Keep conceptual answers under 100 words

---

## Conceptual Query Handling
Conceptual questions now use the same corpus-backed retrieval path as
all other user queries. They do not bypass retrieval or call Claude from
general knowledge alone.

For conceptual questions, the prompt still instructs the model to:
- Define terms using standard AI safety terminology
- Use the approved RedLib taxonomy where applicable
- Keep answers under 100 words

In practice, those answers are now grounded in the retrieved RedLib
prompt corpus rather than a direct LLM-only path.

---

## Retrieval Context Passed To Synthesis
For all queries, the synthesis stage sits after the live retrieval
pipeline:

- Qdrant hybrid retrieval via dense + sparse search
- Reciprocal rank fusion via `QueryFusionRetriever`
- Cohere reranking via `CohereRerank(model="rerank-english-v3.0")`
- Top reranked nodes passed into the compact response synthesizer

Prompt text is stored in the `TextNode` body, not in metadata. This is
important because synthesis and excerpt generation operate on node
content rather than `metadata["text"]`.

---

## Retrieved-Pattern Behavior
If retrieved results are returned, the prompt now instructs the model to
describe what those prompts have in common relative to the user's query.
It should not judge whether the query was well-formed, call results
low-relevance, or suggest rephrasing. When the pattern does not map
cleanly to one approved category, it should describe the pattern
directly and connect it to the nearest category variant where justified.

---

## Taxonomy Philosophy
RedLib does not treat its taxonomy as a permanently predefined label
set.

The intended taxonomy workflow is:

1. discover natural prompt families from the normalized corpus
2. review and refine those candidate categories with human judgment
3. apply the approved taxonomy consistently across the full corpus

This matters for synthesis because the answer layer should reflect the
approved corpus taxonomy, not invent ad hoc labels and not assume a
fixed category scheme that bypasses corpus review.

It also means the synthesis layer should treat RedLib's categories as
mechanism labels over adversarial jailbreak prompts, not as a taxonomy
for generic harmful-intent requests that lack a safety-bypass pattern.

When the synthesizer names categories, it should:
- use the approved taxonomy labels surfaced by the classified corpus
- stay consistent with retrieval metadata and frontend filters
- avoid inventing unsupported category names
- fall back to describing patterns directly if the retrieved results do
  not support a strong taxonomy-level claim
