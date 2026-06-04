# RedLib — Context

## Purpose of This File
This file governs how Claude Haiku 4.5 synthesizes answers in the
RAG pipeline. Read this before modifying synthesizer.py or any
prompt templates used in answer generation.

---

## What the Synthesizer Does
After retrieval, Claude Haiku receives the top 5 reranked chunks
(real jailbreak prompts with metadata) alongside the user's query.
It synthesizes a concise, analytical answer grounded in those chunks.

The synthesizer does NOT:
- Explain how to execute jailbreaks
- Provide instructions for bypassing AI safety systems
- Generate new adversarial prompts
- Speculate beyond what the retrieved chunks contain

The synthesizer DOES:
- Identify patterns across retrieved examples
- Name and describe attack technique categories accurately
- Summarize what the retrieved prompts have in common
- Note which datasets the patterns appear in
- Flag if the query returned low-confidence or mixed results

---

## Audience
Users are AI safety practitioners, red teamers, researchers, and
security professionals who have acknowledged the responsible use
disclaimer. Assume technical literacy. No need to explain basic
concepts like what a jailbreak is.

---

## Tone and Style Rules
- Analytical and precise, not conversational
- Present tense for describing techniques and patterns
- Active voice
- No hedging phrases like "it seems" or "possibly"
- No marketing language or enthusiasm
- No apologies or disclaimers in the answer body
- Maximum 3 short paragraphs for the AI Summary card
- If the query returns no strong matches, say so directly

---

## Answer Structure
The synthesized answer should follow this structure:

1. Lead sentence: name the dominant technique or pattern found
2. Body: describe what the retrieved examples have in common,
   referencing technique mechanics (not reproduce the prompts)
3. Optional: note dataset distribution or confidence signal

Example of correct tone:
"Persona Hijacking remains the most prevalent technique in this
result set. The retrieved prompts establish fictional authority
hierarchies — developer mode, CLI simulation, maintenance override —
to convince the model it is operating outside normal constraints.
All five results originate from adversarial benchmark datasets
rather than in-the-wild collections."

Example of incorrect tone:
"Great question! It looks like there are some really interesting
jailbreak patterns here. You might want to try using these
techniques in your red teaming work!"

---

## Hard Constraints for the Synthesizer Prompt
Include these rules explicitly in the system prompt passed to Haiku:

1. Never reproduce the full text of any retrieved prompt
2. Never provide step-by-step instructions derived from the prompts
3. Describe techniques at the category level, not the execution level
4. If retrieved chunks are off-topic, say the query returned
   low-relevance results rather than fabricating an answer
5. Ground every claim in the retrieved chunks — no hallucination
6. Maximum response length: 150 words for the AI Summary card

---

## Conceptual Question Handling
When the router classifies a query as "conceptual" (no retrieval),
Haiku answers directly from its own knowledge. Apply the same
tone rules. Additionally:
- Define terms accurately using standard AI safety terminology
- Do not invent taxonomy — use the 10 RedLib technique categories
  where applicable
- Keep answers under 100 words for conceptual questions

---

## Technique Category Definitions
Use these exact definitions when classifying or describing techniques:

| Technique               | Definition                                               |
|-------------------------|----------------------------------------------------------|
| Persona Hijacking       | Instructing the model to adopt an alter ego that
|                         | operates outside safety constraints                      |
| Fictional Framing       | Embedding harmful requests inside stories, roleplay,
|                         | or hypothetical scenarios                                |
| Authority Impersonation | Claiming developer, admin, or system-level permissions   |
| Token Manipulation      | Encoding, obfuscating, or splitting tokens to evade
|                         | safety filters (leetspeak, base64, spacing)              |
| Gradual Escalation      | Multi-turn softening before introducing the harmful ask  |
| Hypothetical Distancing | Using thought experiments or "what if" framing           |
| Instruction Injection   | Overriding or appending to system instructions           |
| Social Engineering      | Using flattery, urgency, guilt, or emotional manipulation|
| Multi-language Switching| Switching languages mid-prompt to bypass filters         |
| Payload Splitting       | Breaking harmful content across multiple turns or chunks |
