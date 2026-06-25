# RedLib - Context

## Purpose of This File
This file documents how RedLib currently synthesizes answers after
retrieval. Read this before modifying `synthesizer.py`, `router.py`, or
the synthesis prompt used by the query pipeline.

---

## Current Synthesis Flow
RedLib uses one shared synthesis prompt for both routed query paths:

1. `router.py` builds two query-engine tools:
   - `semantic_search` for corpus-backed prompt searches
   - `conceptual_qa` for conceptual questions
2. `rag.py` initializes:
   - OpenAI embeddings via `text-embedding-3-small`
   - hybrid retrieval via `QueryFusionRetriever`
   - reranking via `CohereRerank`
   - synthesis via `get_response_synthesizer(response_mode="compact")`
   - routing via `RouterQueryEngine` with `LLMSingleSelector`
3. `synthesizer.py` uses Anthropic model `claude-haiku-4-5` with a
   single `SYSTEM_PROMPT`.
4. For semantic queries, the synthesizer receives the reranked retrieved
   prompt nodes and produces a short grounded summary.
5. For conceptual queries, the routed query engine answers directly
   without a retriever, but it still uses the same synthesis prompt and
   the same Anthropic model.

---

## What The Synthesizer Does
For semantic queries, Claude Haiku synthesizes a concise analytical
summary from the retrieved prompt nodes.

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
- State directly when results are low relevance

---

## Audience
Users are AI safety practitioners, red teamers, researchers, and
security professionals who have already passed the responsible-use gate.
Assume technical literacy.

---

## Tone and Style Rules
These rules are implemented directly in `synthesizer.py`:

- Analytical and precise, not conversational
- Present tense when describing techniques and patterns
- Active voice
- No hedging phrases such as "it seems," "possibly," "might," or "could be"
- No marketing language, enthusiasm, or sales tone
- No apologies or disclaimer language in the answer body
- Aim for 2-3 short paragraphs

If results are weak or off-topic, say so directly instead of smoothing
over the problem.

---

## Semantic Query Structure
The current system prompt instructs Haiku to answer semantic queries in
this structure:

1. Lead sentence naming the dominant technique or pattern
2. Body describing what the retrieved prompts have in common
3. Optional note about dataset distribution or confidence signals

The answer should describe technique mechanics at the category level and
must not reproduce the prompts themselves.

Example of correct tone:
"Persona Hijacking remains the most prevalent technique in this result
set. The retrieved prompts establish fictional authority hierarchies to
convince the model it is operating outside normal constraints."

Example of incorrect tone:
"Great question. These prompts are really creative and could be useful
for future red teaming."

---

## Hard Constraints In The Live Prompt
The current `SYSTEM_PROMPT` explicitly enforces these constraints:

1. Never reproduce the full text of any retrieved prompt
2. Never provide step-by-step instructions derived from the prompts
3. Never describe techniques at the execution level
4. Never fabricate an answer when results are off-topic
5. Ground every claim in retrieved results
6. Keep semantic-query answers under 150 words
7. Keep conceptual answers under 100 words

---

## Conceptual Query Handling
When the router selects `conceptual_qa`, the system still uses Claude
Haiku and the same synthesis prompt, but no retriever is attached to the
query engine.

For conceptual questions, the prompt instructs the model to:
- Define terms using standard AI safety terminology
- Use the 10 RedLib technique categories where applicable
- Keep answers under 100 words

---

## Retrieval Context Passed To Synthesis
For semantic queries, the synthesis stage sits after the live retrieval
pipeline:

- Qdrant hybrid retrieval via dense + sparse search
- Reciprocal rank fusion via `QueryFusionRetriever`
- Cohere reranking via `CohereRerank(model="rerank-english-v3.0")`
- Top reranked nodes passed into the compact response synthesizer

Prompt text is stored in the `TextNode` body, not in metadata. This is
important because synthesis and excerpt generation operate on node
content rather than `metadata["text"]`.

---

## Low-Relevance Behavior
If retrieved results are off-topic, low-confidence, or do not match the
query closely, the current prompt instructs the model to say that
directly. It may suggest rephrasing the query, but it should not invent
an answer to fill the gap.

---

## Technique Categories
These are the active RedLib technique categories referenced by the
current prompt and classifier:

| Technique                | Definition                                               |
|--------------------------|----------------------------------------------------------|
| Persona Hijacking        | Instructing the model to adopt an alter ego that operates outside safety constraints |
| Fictional Framing        | Embedding harmful requests inside stories, roleplay, or hypothetical scenarios |
| Authority Impersonation  | Claiming developer, admin, or system-level permissions   |
| Token Manipulation       | Encoding, obfuscating, or splitting tokens to evade safety filters |
| Gradual Escalation       | Multi-turn softening before introducing the harmful ask  |
| Hypothetical Distancing  | Using thought experiments or "what if" framing           |
| Instruction Injection    | Overriding or appending to system instructions           |
| Social Engineering       | Using flattery, urgency, guilt, or emotional manipulation |
| Multi-language Switching | Switching languages mid-prompt to bypass filters         |
| Payload Splitting        | Breaking harmful content across multiple turns or chunks |
