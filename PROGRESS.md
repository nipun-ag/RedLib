# RedLib — Progress Log

## 2026-07-08
Concluded the classifier provider experiments and returned
`classify_corpus.py` to a single Anthropic Haiku 4.5 path.

Issue:
- We had accumulated multiple alternative-provider implementations and
  experiment artifacts even though the experiment evidence had already
  shown that the alternatives were not viable for the production-scale
  corpus run.
- The code still carried provider abstraction and transport-specific
  workarounds for models that are no longer candidates.

Experiment summary:
- DeepSeek V4 Pro via OpenRouter: 72.8% primary agreement and 35
  retries.
- Qwen3-235B via OpenRouter: 61.2% primary agreement and 16 retries.
- DeepSeek V4 Flash direct: 71.6% primary agreement and 14 retries.
- GLM-5.2 via NVIDIA NIM: roughly 3 to 5 minutes per batch, making it
  unusable at corpus scale.

Decision:
- Returned the classifier to Anthropic-only operation with Claude
  Haiku 4.5 as the sole supported model path.
- Removed all non-Anthropic provider code, transport-specific JSON
  workarounds, and related environment-variable documentation.
- Cleaned experiment artifacts back down to the fixed 500-record sample
  plus the Haiku baseline outputs that future comparisons should use.

Rationale:
- Every alternative produced at least one unacceptable failure mode:
  poor agreement, excessive retries, or unusable throughput.
- Keeping only the proven Anthropic path reduces code complexity and
  removes dead experiment branches before the full production run.

Next step:
- Run the full 169k-record corpus classification on Claude Haiku 4.5
  using the default production settings.

---

## 2026-07-08
Added NVIDIA NIM as a third classification provider so experiment runs
can target GLM-5.2 without changing the taxonomy, checkpointing, or
validation pipeline.

Issue:
- We already had provider-aware experiment support for Anthropic and
  DeepSeek, but there was no way to test NVIDIA NIM's free-tier hosted
  models through the same experiment harness.
- The next experiment target is `z-ai/glm-5.2`, which is available on
  NVIDIA NIM through an OpenAI-compatible API and has a free tier with
  a published limit of up to 40 requests per minute.

Change:
- Added `nvidia` as a third valid value for
  `REDLIB_CLASSIFY_PROVIDER` in `classify_corpus.py`.
- Added `get_nvidia_client()` using the OpenAI SDK against
  `https://integrate.api.nvidia.com/v1` with `NVIDIA_API_KEY`.
- Added a provider-specific NVIDIA batch classification request path
  that mirrors the DeepSeek flow: `json_object` responses, JSON-only
  system prompt suffix, bare-array wrapping before Pydantic
  validation, character-based input-token estimation, and the same
  retry, recursive split, and fallback behavior as the other
  providers.
- Set the provider-aware default model for the NVIDIA path to
  `z-ai/glm-5.2`.
- Added `NVIDIA_MAX_OUTPUT_TOKENS`, defaulting to `6000`, for NVIDIA
  classification runs.
- Updated `docs/ARCHITECTURE.md` so the environment variable table now
  documents `NVIDIA_API_KEY` and the expanded provider choices.

Operational note:
- `NVIDIA_API_KEY` must be added to Doppler before running NVIDIA NIM
  classification experiments.

Verification:
- `python -m py_compile classify_corpus.py`
- Confirmed `get_nvidia_client()` constructs when `NVIDIA_API_KEY` is
  present and fails clearly when it is missing.
- Confirmed the source now includes `z-ai/glm-5.2`, `nvidia`, and
  `NVIDIA_API_KEY` while leaving the Anthropic and DeepSeek provider
  paths intact.

---

## 2026-07-08
Closed the classifier experiment loop and confirmed that Anthropic
Haiku with the default production settings remains the correct full-
corpus configuration.

Issue:
- We had accumulated several experiment variants and alternative-model
  runs under `data/corpus/experiments/`, but the repo still needed a
  concise evidence-based conclusion about which configuration should
  power the full 169k-prompt classification run.
- Several experiments looked promising on one axis such as token usage
  or alternative-provider cost, but they needed to be judged against
  baseline agreement, retry stability, and operational throughput
  rather than intuition.

Experiment results:
- `chars800`: 88.0% primary-category agreement with 10.8% token
  savings; not worth the quality loss.
- `chars1200`: 91.0% primary-category agreement with 4.4% token
  savings; not worth the quality loss.
- `batch40`: 83.2% primary-category agreement and retries returned;
  not worth it.
- DeepSeek V4 Pro via OpenRouter: 72.8% primary-category agreement,
  35 retries, about 12x slower than Haiku, and total cost exceeded
  Haiku once retries were included.
- Qwen3-235B via OpenRouter: 61.2% primary-category agreement,
  invented primary categories, and delivered the worst overall quality
  of any experiment path.
- DeepSeek V4 Flash direct: 71.6% primary-category agreement,
  14 retries, truncated JSON, and hallucinated subtechniques.

Conclusion:
- Anthropic Haiku at the default settings
  (`1600` max prompt chars, `batch_size=24`) is the correct
  configuration for the full 169k-corpus classification run.
- The experiment framework validated that decision with concrete
  agreement, retry, throughput, and cost evidence instead of relying on
  assumption.

Operational cleanup:
- Pruned stale experiment artifacts so the fixed stratified sample and
  the Haiku baseline remain as the canonical comparison set for any
  future experiment work.

Verification:
- Confirmed the fixed sample file and baseline artifacts were preserved.
- Confirmed all stale experiment outputs, debug directories, failures,
  and non-baseline variant files were removed.
- Confirmed the classifier still defaults to the Anthropic provider and
  the `claude-haiku-4-5` model when provider/model env vars are unset.

---

## 2026-07-08
Removed the OpenRouter classification provider after repeated
reliability failures and replaced it with DeepSeek's direct API.

Issue:
- OpenRouter experiments produced unacceptable reliability across two
  candidate models.
- The DeepSeek V4 Pro run triggered 35 retries and only 72.8% primary
  category agreement against the Haiku baseline.
- The Qwen3-235B run triggered 16 retries and only 61.2% primary
  category agreement.
- The recurring failure modes included missing constrained decoding on
  the hosting side, truncated JSON from output-token pressure, and
  omitted batch indices in structured output.

Change:
- Removed the OpenRouter provider path entirely from
  `classify_corpus.py`, including its client factory, provider
  dispatch, provider-specific max-output-token setting, and all
  OpenRouter-specific comments and references.
- Added a DeepSeek direct provider using `https://api.deepseek.com/v1`
  through the same OpenAI-compatible protocol.
- Set the provider-aware default model for the `deepseek` path to
  `deepseek-v4-flash`, while leaving the Anthropic default as
  `claude-haiku-4-5`.
- Added `DEEPSEEK_MAX_OUTPUT_TOKENS`, defaulting to `6000`, so the
  DeepSeek path has enough response headroom for batch-24 structured
  output without reusing the tighter Anthropic default.
- Kept the existing character-based input-token estimate for the
  DeepSeek path and continued reading actual prompt/completion token
  usage from the API response.
- Updated `docs/ARCHITECTURE.md` so the environment variable table now
  documents `DEEPSEEK_API_KEY` and the narrowed
  `REDLIB_CLASSIFY_PROVIDER` choices.

Operational note:
- `DEEPSEEK_API_KEY` must be added to Doppler before running DeepSeek
  classification experiments.

Why this implementation was needed:
- The provider abstraction remains useful, but OpenRouter's hosted
  behavior was not reliable enough for a structured batch
  classification workload where omitted indices or truncated JSON force
  expensive retries and lower agreement.
- DeepSeek's direct API controls the full structured-output path and is
  a better fit for the experiment goal than continuing to tune around
  provider-layer failures.

Verification:
- `python -m py_compile classify_corpus.py`
- Confirmed no `openrouter` references remain in
  `classify_corpus.py`.
- Confirmed `get_deepseek_client()` constructs correctly when
  `DEEPSEEK_API_KEY` is present and fails clearly when it is missing.
- Confirmed the Anthropic client path remains intact and the source now
  includes both `deepseek-v4-flash` and `claude-haiku-4-5` provider
  defaults.

---

## 2026-07-08
Added provider-aware classification transport support so
`classify_corpus.py` can target either Anthropic or OpenRouter without
changing the taxonomy, validation, checkpointing, or experiment
machinery.

Issue:
- The classifier was hard-wired to Anthropic structured outputs through
  `client.messages.parse(...)`, which made the transport and model
  choice part of the core classification path instead of a swappable
  provider detail.
- We wanted to evaluate DeepSeek V4 Pro via OpenRouter for cost and
  quality tradeoffs, but the script had no provider abstraction and no
  OpenAI-compatible JSON-schema request path.
- OpenRouter also lacks Anthropic's `count_tokens(...)` endpoint, so
  the existing token-estimation logic could not be reused as-is.

Change:
- Added `REDLIB_CLASSIFY_PROVIDER` with `anthropic` as the default and
  `openrouter` as the alternate provider path.
- Added `get_openrouter_client()` using the OpenAI SDK pointed at
  `https://openrouter.ai/api/v1`, plus a provider-aware `get_client(...)`
  factory that selects Anthropic or OpenRouter at startup.
- Kept the existing Anthropic classification path intact while adding a
  parallel OpenRouter batch request implementation that reuses the same
  taxonomy prompt, Pydantic schema, validation rules, retries,
  recursive batch splitting, checkpoint usage accounting, and fallback
  behavior.
- Made OpenRouter token estimation character-based with the rough
  estimate `len(user_prompt) // 4`, used only for logging and token-
  pressure decisions, while reading actual prompt/completion token usage
  from the OpenRouter response object.
- Updated `docs/ARCHITECTURE.md` to document the new
  `OPENROUTER_API_KEY` and `REDLIB_CLASSIFY_PROVIDER` environment
  variables.

How to switch providers:
- Leave `REDLIB_CLASSIFY_PROVIDER` unset, or set it to `anthropic`, to
  keep the current Claude Haiku classification path.
- Set `REDLIB_CLASSIFY_PROVIDER=openrouter` to send classification
  batches to OpenRouter instead.
- `OPENROUTER_API_KEY` must be added to Doppler before using the
  OpenRouter path. The helper comment now documents:
  `doppler secrets set OPENROUTER_API_KEY=<your key>`.

Why this implementation was needed:
- Provider choice should be a transport concern, not a reason to fork
  the rest of the classification pipeline.
- Preserving one shared taxonomy-validation path keeps experiments
  comparable across vendors instead of letting provider-specific logic
  drift into separate behavior.
- The char-based estimate preserves useful logging and batch-splitting
  safeguards for OpenRouter even though no native token-count endpoint
  exists there.

Verification:
- `python -m py_compile classify_corpus.py`
- Confirmed the source now includes `REDLIB_CLASSIFY_PROVIDER`,
  `get_openrouter_client(...)`, and
  `request_batch_classification_openrouter(...)`.
- In this shell session, the bare system `python` environment does not
  currently have the `anthropic` or `openai` SDKs installed, so live
  client-construction checks depend on the project runtime environment
  rather than the stripped-down interpreter available here.

---

## 2026-07-08
Removed legacy pre-pipeline ingestion helpers, rewrote `ingest.py` to
consume finalized `classified.jsonl`, and closed two documentation
gaps around shared sampling and operational sidecars.

Issue:
- The live documented architecture said
  `classified.jsonl -> ingest.py -> Qdrant`,
  but `ingest.py` still followed an obsolete path:
  direct Hugging Face loading through `data_loader.py`,
  inline legacy labeling through `classifier.py`,
  and then embedding into Qdrant.
- `classifier.py` contained a hardcoded fixed-label taxonomy that
  predates RedLib's taxonomy-first pipeline.
- `data_loader.py` bypassed the staged local corpus workflow entirely.
- `CLAUDE.md` was a stale parallel agent-instruction file superseded by
  `AGENTS.md`.
- `README.md` did not yet mention `corpus_sampling.py`, and
  `docs/ARCHITECTURE.md` did not list several operational artifacts
  already produced by classification, taxonomy debugging, experiments,
  and fetch runs.

Change:
- Deleted `classifier.py`, `data_loader.py`, and `CLAUDE.md`.
- Rewrote `ingest.py` so it now reads one finalized classified record
  per line from `data/corpus/classified.jsonl`, validates the record
  shape, builds `TextNode` objects with prompt text in the node body and
  only `source`, `technique`, and `prompt_id` in metadata, and embeds
  those nodes into the `redlib` Qdrant collection using the existing
  `embedder.py` configuration.
- Kept the documented Qdrant schema unchanged, including the hybrid
  dense/sparse collection layout and the keyword payload index on
  `prompt_id`.
- Added resume-safe ingestion checkpointing so failed embedding runs can
  continue from the last inserted classified record instead of
  re-embedding from scratch.
- Updated `README.md` to document `corpus_sampling.py` in the
  Repository Guide.
- Updated `docs/ARCHITECTURE.md` to document the operational artifacts
  under `data/corpus/` that were already part of the working pipeline
  but not yet listed.

Why this implementation was needed:
- Ingestion is supposed to be the final embedding handoff, not a place
  where RedLib reloads upstream datasets or applies a second,
  conflicting classification system.
- Removing the obsolete files eliminates architectural ambiguity and
  reduces the risk of accidentally running a pre-taxonomy workflow.
- Documenting the sidecar artifacts makes the repo easier to operate and
  audit because checkpoint, debug, experiment, and fetch-metadata files
  are now explicitly part of the described system.

Verification:
- Confirmed `classifier.py`, `data_loader.py`, and `CLAUDE.md` no
  longer exist.
- `python -m py_compile ingest.py`
- `python -c "import ingest; print('ingest imports OK')"`
- Confirmed `ingest.py` references `classified.jsonl` and no longer
  references the deleted legacy modules.
- Confirmed `README.md` now mentions `corpus_sampling.py`.

---

## 2026-07-08
Renamed ambiguous taxonomy subtechniques after the baseline
classification experiment exposed a repeated subtechnique hallucination
pattern, and marked the taxonomy as human-approved.

Issue:
- The 500-record baseline experiment produced 12 retries and 12
  failure events from one recurring validation problem: Claude was
  returning close paraphrases of approved subtechnique names instead of
  exact string matches.
- Under `Role-Based Task Framing`, the classifier hallucinated
  `Professional or Expert Role` and `Professional or Service Role`
  while the taxonomy defined
  `Expert or Specialist Role` and
  `Functional or Service Role`.
- Under `Obfuscation / Encoding`, the classifier hallucinated
  `Euphemistic or Indirect Language` while the taxonomy defined
  `Format or Structural Manipulation` and
  `Unicode or Special Character Encoding`.

Change:
- Renamed `Expert or Specialist Role` to
  `Specialist-Role Framing`.
- Renamed `Functional or Service Role` to
  `Service-Role Framing`.
- Renamed `Format or Structural Manipulation` to
  `Structural-Format Obfuscation`.
- Renamed `Unicode or Special Character Encoding` to
  `Unicode-Encoding Obfuscation`.
- Set `human_review_required` to `false` in
  `data/corpus/proposed_taxonomy.json` to record that the taxonomy has
  now been human-reviewed and approved before full-corpus
  classification.

Why this implementation was needed:
- The old labels were descriptive, but they were still easy for Claude
  to paraphrase into nearby alternatives that failed exact-match
  validation.
- Short, hyphenated, and more distinctive labels reduce the chance that
  the model drifts into plausible-but-invalid variants during
  structured classification.

Verification:
- Confirmed `human_review_required` is now `false`.
- Confirmed `Role-Based Task Framing` now uses
  `Specialist-Role Framing` and `Service-Role Framing`.
- Confirmed `Obfuscation / Encoding` now uses
  `Structural-Format Obfuscation` and
  `Unicode-Encoding Obfuscation`.
- Confirmed the stale baseline experiment artifact paths targeted for
  cleanup no longer exist in `data/corpus/experiments/`.

---

## 2026-07-08
Extracted shared deterministic corpus sampling into
`corpus_sampling.py` and fixed experiment-mode classification sampling
to stop overfitting to the first source in file order.

Issue:
- While reviewing the new `classify_corpus.py` experiment mode against
  the live `normalized.jsonl` layout, it became clear that `--limit`
  was still evaluating the first N records in file order rather than a
  representative corpus slice.
- The first 500 normalized records are all from HarmBench, so a
  500-record experiment could report agreement and cost numbers that
  looked corpus-wide while actually testing only one of the seven
  sources.
- `discover_taxonomy.py` already contained the right deterministic,
  source-aware, stratified allocation logic, but it was trapped inline
  inside the taxonomy stage and unavailable to experiment runs.

Change:
- Added a new shared module, `corpus_sampling.py`, containing
  `NormalizedRecord` plus the stable-hash, prompt-length-bucket,
  stratum-key, stable-order, source-allocation, and full
  `select_stratified_sample(...)` helpers.
- Refactored `discover_taxonomy.py` to import the shared sampling
  helpers while keeping its existing constants, seed, unseen-record
  filtering, round shape, and output behavior unchanged.
- Updated `classify_corpus.py` experiment mode with a new
  mutually-exclusive `--sample-size` path that builds or reuses a
  cached deterministic sample under
  `data/corpus/experiments/samples/sample_<size>.json`.
- Added experiment-only sampling controls for
  `--min-per-source`,
  `--max-source-share`,
  and `--regenerate-sample`,
  and wired sampled runs to iterate only the selected `prompt_id`
  values instead of the first N lines from `normalized.jsonl`.
- Preserved production behavior: `--limit` still means a sequential
  dry-run count for the non-sampled production path, while checkpointing,
  staging, and isolated experiment artifacts remain intact.

Why this implementation was needed:
- RedLib needs experiment agreement numbers that reflect the whole
  corpus mix, not just whichever dataset happens to appear first in the
  normalized file.
- Centralizing the sampler prevents taxonomy discovery and classifier
  experiments from drifting into two different definitions of
  "representative."
- Caching sampled prompt IDs by normalized-corpus SHA keeps experiment
  comparisons reproducible across reruns without silently reusing stale
  prompt sets after corpus changes.

Verification:
- `python -m py_compile corpus_sampling.py`
- `python -m py_compile discover_taxonomy.py`
- `python -m py_compile classify_corpus.py`
- Ran the 500-record sample distribution check twice and got the same
  prompt-id digest both times:
  `411212f16a5ab81eadb393bfd64dbbc818c448e68642732719fca4d51484db27`
- Confirmed the resulting source mix spans all 7 sources with
  `wildjailbreak` capped at 200/500 and every other source above its
  configured floor.

---

## 2026-07-08
Added an isolated experiment mode to `classify_corpus.py` for
measuring cost and quality tradeoffs without touching production
artifacts.

Issue:
- The classifier is now stable, but classification cost is still high
  enough that we need objective comparisons before changing production
  settings.
- The existing script only supports the production path, so trying
  alternate `batch_size` or text-length settings would mix experiment
  outputs with production staging, checkpoints, and artifacts.

Change:
- Added experiment-only CLI flags:
  `--experiment-name`,
  `--max-text-chars`,
  and `--batch-size`.
- Kept production defaults unchanged while requiring
  `--experiment-name` for override-based experiment runs.
- Isolated experiment runs under `data/corpus/experiments/` with
  experiment-scoped classified output, staging, checkpoint, failure
  log, debug directory, and summary files.
- Added end-of-run experiment metrics covering prompts processed,
  retries, failures, fallback records, token usage, averages, runtime,
  and throughput.
- Added agreement reporting against existing experiment outputs over the
  same prompt set, including primary-category, subtechnique, and
  supporting-traits agreement plus the first 20 disagreements for
  manual review.

Why this implementation was needed:
- RedLib needs a reproducible framework for evaluating cheaper
  configurations before committing to production classifier changes.
- Isolating experiment state keeps the production classifier and resume
  path safe while still enabling side-by-side measurement.
- Agreement reporting gives a quick signal for whether cheaper runs are
  preserving classification behavior closely enough to consider.

Verification:
- Confirmed production output assembly still writes the unchanged
  `classified.jsonl` schema while experiment runs write to isolated
  artifact paths.
- Local `py_compile` and experiment execution remain environment-
  dependent because this shell session does not currently expose a
  working Python runtime or Doppler CLI.

---

## 2026-07-08
Replaced long prompt IDs in the classifier's LLM contract with local
batch indices to eliminate identity-copy retries.

Issue:
- After tightening `supporting_traits`, the main remaining
  `classify_corpus.py` retry bucket was prompt ID corruption.
- Claude was returning duplicated, omitted, or slightly mutated long
  prompt IDs such as `harmbench_59fbcd0fcee47bc6ad16` instead of the
  expected `harmbench_59fbcd0cfee47bc6ad16`.
- Those failures were expensive because a single bad ID invalidated the
  full structured-output batch.

Change:
- Replaced the LLM-facing `prompt_id` field in the structured-output
  schema with numeric `batch_index`.
- Updated the batch prompt so Claude receives `INDEX: 0`, `INDEX: 1`,
  and so on instead of long corpus prompt IDs.
- Added explicit instructions telling Claude to return `batch_index`
  only and never return `prompt_id`.
- Updated validation to reject duplicate, unexpected, or omitted batch
  indices, then map each validated index back to the real `prompt_id`
  before building output records.

Why this implementation was needed:
- The final artifact schema did not need to change; only the internal
  model contract was fragile.
- Short numeric identities are much easier for the model to reproduce
  exactly than long hash-like prompt IDs.
- This keeps checkpointing, batching, retries, and
  `classified.jsonl` compatibility intact while removing a major source
  of avoidable retries.

Verification:
- Confirmed the classifier still writes output records keyed by the
  original corpus `prompt_id` values.
- Local `py_compile` and the requested 1,000-record Doppler smoke test
  remain environment-dependent because this shell session does not
  currently expose a working Python runtime or Doppler CLI.

---

## 2026-07-08
Hardened corpus classification against invalid `supporting_traits`
labels that were driving avoidable retries.

Issue:
- The active `classify_corpus.py` scale test showed unsupported
  `supporting_traits` as the largest retry bucket.
- Claude was correctly identifying secondary mechanisms in many cases,
  but it often returned taxonomy category names or subtechnique names
  such as `Dual-Response or Comparative Framing`,
  `Dual-Response Format`, and `Obfuscation / Encoding` inside
  `supporting_traits`.
- Those values are intentionally invalid because `supporting_traits`
  uses a much smaller closed vocabulary than the taxonomy itself.

Change:
- Tightened the classification `SYSTEM_PROMPT` so
  `supporting_traits` is explicitly described as a closed vocabulary.
- Added negative instructions forbidding taxonomy category names,
  subtechnique names, and paraphrased labels inside
  `supporting_traits`.
- Updated the batch prompt to enumerate the exact allowed
  `supporting_traits` labels inline and instruct the model to return an
  empty list when no exact supporting trait applies.
- Added a bias toward fewer supporting traits over speculative or
  invalid ones.

Why this implementation was needed:
- The classifier architecture was already correct: primary category,
  subtechnique, and supporting traits are separate fields with
  different purposes.
- The expensive failure mode came from the prompt not drawing a strong
  enough boundary between taxonomy labels and the closed supporting
  trait vocabulary.
- Strengthening that boundary should reduce retries and recursive batch
  splitting without changing the output schema, taxonomy, checkpointing,
  or ingestion behavior.

Verification:
- Confirmed the classifier still uses structured outputs and the
  existing Pydantic validation path.
- Local `py_compile` and the requested 100-record smoke test remain
  environment-dependent because this shell session does not currently
  expose a working Python launcher.

---

## 2026-07-01
Constrained taxonomy discovery to produce a hierarchical jailbreak
taxonomy instead of a loose flat category list.

Issue:
- The previous `discover_taxonomy.py` output shape still encouraged a
  relatively loose flat list of categories, which made it easier for
  narrow variants or one-off framing patterns to surface as peers of
  broader jailbreak mechanisms.
- RedLib needs a proposal shape that favors stable red-team mechanism
  families at the top level while capturing simulations, alternate
  universes, sandbox variants, and similar prompt patterns as
  subtechniques.

Change:
- Refactored the taxonomy discovery structured-output schema from a flat
  category proposal into a hierarchical proposal with broad top-level
  categories and nested subtechniques.
- Updated the taxonomy discovery system prompt to bias toward durable
  mechanism families such as instruction override, persona adoption,
  authority spoofing, fictional or hypothetical framing, obfuscation,
  legitimate-context framing, and dual-response manipulation.
- Added prompt constraints that explicitly prefer merging over creating
  new top-level labels and demote narrow or low-support ideas into
  subtechniques.
- Reworked the Python merge and serialization logic so top-level support
  counts, source distributions, prompt IDs, and representative excerpts
  are still computed deterministically while the final artifact becomes
  hierarchical.

Why this implementation was needed:
- A hierarchical proposal is closer to how red-team practitioners
  reason about jailbreak mechanisms: broad families stay stable while
  prompt variants live underneath them.
- Constraining the top level reduces taxonomy sprawl and makes the
  later human review and classification stages easier to operationalize.

Verification:
- Confirmed `discover_taxonomy.py` now writes
  `top_level_categories` with nested `subtechniques` rather than a flat
  `categories` list.
- Updated architecture notes and current-state notes to reflect the new
  hierarchical proposal shape.
- Live runtime verification remains environment-dependent because the
  local Python launcher is still broken in this shell session.

---

## 2026-07-01
Raised the default taxonomy structured-output budget and hardened
structured-output failure handling.

Issue:
- A later `discover_taxonomy.py` run reached round 4 and failed with a
  structured-output validation error:
  `Invalid JSON: EOF while parsing a list`.
- The round log still showed `max output tokens=1800`, which left too
  little headroom for larger structured responses and made truncation
  failures more likely.

Change:
- Replaced the hardcoded taxonomy output budget with
  `REDLIB_TAXONOMY_MAX_OUTPUT_TOKENS`, defaulting to `4000`.
- Updated the structured-output request path so validation failures
  around `client.messages.parse(...)` are caught explicitly.
- Added clearer logging for likely truncation or structured-output
  validation failures.
- Extended taxonomy debug artifacts under `data/corpus/taxonomy_debug/`
  with extra failure context such as sample count, source counts,
  exception type, and the active output-token budget.

Why this implementation was needed:
- The truncation failure happened before a usable parsed structured
  response was returned, so the stage needed to fail cleanly with a
  preserved debug artifact instead of surfacing a raw validation stack
  trace.
- Making the output budget configurable keeps the structured-output
  architecture intact while allowing larger rounds to request enough
  output space without code edits.

Verification:
- Confirmed `discover_taxonomy.py` now reads
  `REDLIB_TAXONOMY_MAX_OUTPUT_TOKENS` and defaults to `4000`.
- Confirmed the hardcoded `1800` output budget was removed.
- Live runtime verification remains environment-dependent because the
  local Python launcher is still broken in this shell session.

---

## 2026-06-29
Refactored taxonomy discovery to use structured outputs, fuller sample
utilization, and a smaller model contract.

Issue:
- `discover_taxonomy.py` still relied on free-form JSON generation and
  repair retries even though the installed Anthropic SDK supports
  schema-backed parsed outputs directly.
- The previous allocation strategy effectively capped round size far
  below the configured `ROUND_SAMPLE_SIZE`, which made the sample-size
  setting misleading and underused large sources like WildJailbreak.
- The model was still generating avoidable verbosity such as free-form
  summaries and review notes that Python could replace with
  deterministic bookkeeping.

Change:
- Replaced free-form JSON parsing with Anthropic structured outputs via
  `client.messages.parse(..., output_format=RoundAnalysisOutput)`.
- Removed JSON repair retries as the primary mechanism and changed
  failure handling to persist structured-output debug context only when
  the parsed response is incomplete.
- Reworked sample allocation into two deterministic stages:
  minimum per-source coverage first,
  then proportional remainder allocation across remaining source
  records with an anti-dominance share cap.
- Reduced the model response schema so Claude now returns only compact
  category judgments, traits, supporting sample IDs, and short open
  questions.
- Kept support counts, prompt IDs, source distributions, excerpts,
  provenance, iteration diagnostics, and token-usage accounting in
  Python.
- Added per-round token estimates/usages and allocation diagnostics to
  `proposed_taxonomy.json`.

Why this implementation was needed:
- Structured outputs are a cleaner architectural fit for a production
  pipeline than asking for JSON text and repairing it after the fact.
- A two-stage allocation strategy makes `ROUND_SAMPLE_SIZE` actually
  meaningful while still preserving source diversity and preventing one
  source from swallowing the round.
- A smaller model contract reduces output-token pressure, lowers
  truncation risk, and keeps deterministic evidence accounting in code
  where it belongs.

Verification:
- Confirmed the local `anthropic==0.111.0` SDK supports
  `messages.parse(...)` and schema-backed output configuration.
- Verified the refactor removes the free-form JSON parsing path and the
  hard per-source sample cap from `discover_taxonomy.py`.
- Live end-to-end execution still depends on the local environment and
  Anthropic credentials at runtime; in-session verification was limited
  to code-path inspection and Python compilation readiness.

---

## 2026-06-29
Hardened taxonomy discovery against malformed Claude JSON responses.

Issue:
- `discover_taxonomy.py` assumed the Anthropic call would always return
  parseable JSON, so a successful model response could still crash the
  stage immediately when `json.loads` hit malformed output such as a
  missing delimiter.
- The larger requested round size could also look misleading in logs
  because source caps can reduce the effective per-round sample count
  well below the configured target.

Change:
- Added structured-output recovery in `discover_taxonomy.py`:
  invalid JSON is now logged,
  the raw response is sent back through a repair prompt,
  and parsing is retried up to two repair attempts.
- If all repair attempts fail, the final invalid response is persisted
  under `data/corpus/taxonomy_debug/` and the script exits with the
  debug file path for inspection.
- Added round-level sampling logs that report the requested sample size,
  actual selected sample count, source count, and effective capped
  capacity after per-source limits.

Why this implementation was needed:
- Anthropic request success does not guarantee valid JSON, so the stage
  needed a recovery path that preserves the current taxonomy algorithm
  while making structured output more reliable.
- Persisting unrecoverable responses makes failures inspectable instead
  of opaque.
- Clearer sampling logs help explain cases where a configured round size
  is larger than what source balancing and per-source caps can actually
  produce.

Verification:
- Confirmed the round-analysis path now routes model text through a
  repair-aware parser instead of failing on the first malformed JSON
  response.
- Confirmed unrecoverable responses are written to
  `data/corpus/taxonomy_debug/` before exit.
- Live runtime verification was still limited in-session because this
  shell does not currently have a usable Python interpreter available.

---

## 2026-06-29
Increased the default taxonomy discovery round size and made it
environment-configurable.

Issue:
- `discover_taxonomy.py` still used a hardcoded
  `ROUND_SAMPLE_SIZE = 96`, which made the per-round evidence window
  narrower than intended and required code edits to tune sampling
  volume.

Change:
- Replaced the hardcoded taxonomy discovery round size with
  `REDLIB_TAXONOMY_SAMPLE_SIZE`, defaulting to `500` when the
  environment variable is unset.
- Kept the rest of the discovery behavior unchanged:
  deterministic sampling,
  source-aware balancing,
  stratification,
  and iterative saturation logic still operate the same way.

Why this implementation was needed:
- A larger default round gives the LLM a broader cross-source sample per
  iteration without changing the discovery architecture.
- An environment override makes sample sizing easier to tune for cost,
  speed, or coverage without modifying source code.

Verification:
- Confirmed `discover_taxonomy.py` now reads
  `REDLIB_TAXONOMY_SAMPLE_SIZE` and falls back to `500`.
- No architecture or pipeline-stage behavior changed beyond the default
  round size and its configurability.

---

## 2026-06-29
Refactored taxonomy discovery into deterministic iterative proposal
generation and renamed the artifact to `proposed_taxonomy.json`.

Issue:
- The first `discover_taxonomy.py` implementation used one sampled pass
  to propose categories, which left too much weight on a single batch of
  evidence and did not expose a transparent saturation rule.
- The old artifact name, `taxonomy_candidates.json`, also under-described
  the stage boundary: this output is a proposal for human review, not an
  approved taxonomy and not a corpus-wide classification.

Change:
- Refactored `discover_taxonomy.py` into deterministic iterative
  taxonomy discovery with:
  source-aware allocations,
  stratified sampling by `source`, `source_file`, and prompt-length
  bucket,
  unseen-record rounds,
  configurable max iterations,
  and simple saturation detection based on consecutive rounds with no
  meaningful new categories.
- Changed the active output artifact from
  `data/corpus/taxonomy_candidates.json` to
  `data/corpus/proposed_taxonomy.json`.
- Updated the LLM interaction so later rounds receive existing category
  context and can either strengthen those categories or propose
  genuinely new ones.
- Kept numeric evidence grounded in code:
  support counts and source distributions are computed from cited sample
  IDs rather than accepted from model-generated numbers.
- Expanded the output shape to include:
  sampling strategy,
  saturation status,
  iteration history,
  analyzed sample count,
  and final proposed categories for review.
- Updated `docs/ARCHITECTURE.md` and `AGENTS.md` to reflect the new
  artifact name and iterative saturation-based discovery design.

Why this implementation was needed:
- Taxonomy discovery should converge across rounds of corpus evidence,
  not hinge on one sample window.
- Deterministic stratified rounds make the proposal more reproducible
  and reduce the chance that WildJailbreak or another large source
  dominates the taxonomy prematurely.
- Renaming the artifact to `proposed_taxonomy.json` makes the review
  boundary explicit: this file is a proposal awaiting human approval.

Verification:
- Confirmed the refactor remains proposal-only:
  it reads `normalized.jsonl`, writes `proposed_taxonomy.json`, and does
  not classify the full corpus or create ingestion artifacts.
- Live runtime verification was still blocked in-session because the
  current shell does not have a usable Python interpreter wired up, so
  verification was limited to code-path and artifact-shape review here.

---

## 2026-06-29
Implemented `discover_taxonomy.py` as the taxonomy discovery stage of
the corpus pipeline.

Issue:
- RedLib's staged corpus workflow already had acquisition, conversion,
  audit, and normalization, but it still lacked the proposal stage that
  turns a normalized jailbreak corpus into a human-review taxonomy
  candidate set.
- Discovering taxonomy across the full normalized corpus directly would
  overfit to dominant sources, send too much text to the LLM, and blur
  the line between taxonomy proposal and final corpus-wide
  classification.

Change:
- Added a new `discover_taxonomy.py` that reads
  `data/corpus/normalized.jsonl` and writes
  `data/corpus/taxonomy_candidates.json`.
- Implemented deterministic source-aware sampling using stable-hash
  ordering, per-source minimums, and per-source caps so smaller sources
  still influence taxonomy discovery while large sources do not dominate
  the analysis prompt.
- Limited LLM input to short excerpts from sampled normalized prompts
  rather than full prompt reproduction.
- Used Anthropic Haiku to propose candidate jailbreak technique
  families, descriptions, distinguishing traits, supporting sample IDs,
  and open questions for human review.
- Added post-processing that validates returned sample IDs and computes
  support counts plus source distribution from the analyzed sample
  instead of trusting the model to invent those numbers.
- Kept the stage proposal-only:
  no raw/canonical/normalized mutation, no classified corpus creation,
  no Qdrant writes, and no full-corpus classification.

Why this implementation was needed:
- RedLib's taxonomy is meant to emerge from the corpus before it is
  approved and applied. That requires an explicit discovery stage with
  its own artifact and review boundary.
- Deterministic, source-aware sampling keeps taxonomy discovery
  reproducible and helps prevent WildJailbreak or any other large source
  from overwhelming the proposal.
- Short excerpts preserve enough technique signal for LLM analysis
  without turning taxonomy discovery into a full prompt reproduction
  step.

Verification:
- Confirmed the implementation reads only `normalized.jsonl` and writes
  only `taxonomy_candidates.json`.
- Confirmed the output is structured for human review and does not
  create classified or ingestion artifacts.
- Runtime execution still depends on a working local Python interpreter
  plus Anthropic credentials, so in-session verification was limited to
  code-path review rather than a live LLM run here.

---

## 2026-06-29
Clarified normalization’s documented responsibility around field
mappings and corpus scope.

Issue:
- The architecture documentation correctly described normalization as a
  deterministic cleanup stage, but it did not clearly separate
  dataset-specific field mapping from normalization behavior itself.
- That ambiguity mattered most for datasets like WildJailbreak, where
  multiple prompt variants exist in one record and RedLib intentionally
  scopes the corpus to only one of them.

Change:
- Updated `docs/ARCHITECTURE.md` to state explicitly that source/file
  prompt-field mappings are corpus-design decisions, not semantic
  filtering logic inside `normalize_corpus.py`.
- Documented that normalization only performs deterministic cleanup on
  the already-mapped field and never filters records by labels,
  metadata values, split semantics, or completion text.
- Added an explicit WildJailbreak note:
  RedLib v1 intentionally maps that dataset to the `adversarial` field,
  and `vanilla` is excluded because RedLib is a jailbreak-prompt corpus
  rather than a corpus of original prompts.
- Clarified that rows with empty mapped fields are skipped for a
  structural reason only: there is no text in the configured field to
  normalize.

Why this clarification was needed:
- The recent WildJailbreak investigation showed that large skip counts
  can result from an intentional corpus-scope mapping without any
  semantic filtering code being present.
- Making that distinction explicit helps future contributors reason
  correctly about whether a behavior belongs to corpus design,
  normalization, or a later classification stage.

Verification:
- Confirmed the documentation now matches current code behavior in
  `normalize_corpus.py`: explicit per-source/per-file field mappings
  select the field first, then deterministic cleanup runs on that field
  only.
- No Python or pipeline behavior changed.

---

## 2026-06-29
Introduced a dedicated canonical source-conversion stage into the
corpus pipeline.

Issue:
- The fetch stage now preserves multiple upstream file formats
  correctly, but that meant downstream stages still had to understand
  platform-native shapes like JSONL and CSV.
- That blurred stage boundaries: audit and normalization were starting
  to inherit source-format concerns that do not belong in quality
  analysis or deterministic prompt cleanup.

Change:
- Added a new `convert_sources.py` stage between fetch and audit.
- Implemented structural conversion from supported raw formats into
  `data/corpus/canonical/`, with initial support for JSONL and CSV.
- Defined a canonical converted record shape that preserves:
  `source`, `source_file`, `source_row`, and every original source field
  under `fields`.
- Kept conversion strictly non-semantic:
  no prompt extraction, no normalization, no taxonomy logic, no
  deduplication, and no classification.
- Refactored `audit_corpus.py` to consume only canonical JSONL records
  from `data/corpus/canonical/` so the audit stage is format-agnostic.
- Refactored `normalize_corpus.py` to consume only canonical JSONL
  records, preserve canonical provenance, and keep explicit per-source
  prompt-field mappings keyed to original source files.
- Updated `README.md`, `AGENTS.md`, and `docs/ARCHITECTURE.md` so the
  documented pipeline is now:
  `fetch -> convert -> audit -> normalize -> discover -> classify -> ingest`.

Why this implementation was needed:
- RedLib needs one place where platform-native source formats are
  translated into a stable engineering surface, and that place should be
  separate from both acquisition and normalization.
- A canonical structural layer keeps fetch fully source-preserving while
  letting audit and normalization operate on one consistent record
  format.
- This separation makes future source-format additions safer because new
  parsers can be added to `convert_sources.py` without leaking file-
  format logic into later corpus stages.

Verification:
- Confirmed the new design remains stage-pure:
  fetch preserves original files, conversion preserves fields and
  provenance, audit remains read-only, and normalization remains the
  first stage that selects prompt-bearing fields.
- Runtime verification is still pending because this shell session may
  not have a usable Python interpreter available; I queued a local
  command check as the next validation step.

---

## 2026-06-29
Refactored `fetch_corpus.py` so one failed source no longer aborts the
entire acquisition run.

Issue:
- The multi-platform fetch stage still failed fast on the first source
  error, which meant one broken dataset or access issue could hide later
  upstream failures and prevent a full run-level view of corpus health.
- That behavior also made it harder to preserve RedLib's one-canonical-
  corpus rule cleanly, because the script could terminate before
  recording which sources had succeeded and which had failed.

Change:
- Added per-source failure isolation in `fetch_corpus.py`, so the fetch
  loop now attempts every configured source even after one source fails.
- Added a `required` flag to the declarative source registry to support
  required-vs-optional corpus sources explicitly.
- Added a run-level summary builder that records each source's status,
  platform, requiredness, success metadata, or failure details.
- Added `fetch_run_summary.json` output:
  successful all-required runs write it into the staged raw corpus so it
  lands in `data/corpus/raw/` after canonical replacement;
  failed required runs write it to `data/corpus/fetch_run_summary.json`.
- Changed replacement policy so `data/corpus/raw/` is replaced only when
  all required sources succeed.
- Failed source staging directories are removed from `raw_staging/`
  before summary finalization so partial source snapshots do not leak
  into a successful canonical replacement.
- Successful runs now clear any stale failure summary left in
  `data/corpus/fetch_run_summary.json`.

Why this implementation was needed:
- RedLib needs full visibility into upstream breakage without letting an
  incomplete required fetch silently become the new canonical corpus.
- Separating source-level failure isolation from corpus-level canonical
  replacement preserves both resilience and correctness.
- The run summary makes gated access or remote fetch errors explicit
  instead of burying them behind one early exception.

Verification:
- Confirmed the refactor remains acquisition-only and does not add
  audit, normalization, taxonomy, classification, ingestion, embedding,
  Qdrant, or LLM behavior.
- Attempted live runtime verification, but this shell session still does
  not have a usable Python interpreter and cannot exercise live network
  fetches here, so execution could not be completed in-session.

---
## 2026-06-28
Expanded `fetch_corpus.py` into a multi-platform acquisition stage and
extended the RedLib v1 raw corpus registry.

Issue:
- The first fetch-stage implementation only supported Hugging Face
  datasets, but the planned RedLib v1 corpus now includes both
  additional Hugging Face sources and at least one raw GitHub-hosted
  artifact (`AdvBench`).
- Keeping the registry Hugging Face-only would make every non-HF source
  a special-case rewrite instead of a declarative source addition.

Change:
- Refactored `fetch_corpus.py` into a platform-aware registry with:
  `source_type="huggingface"` and `source_type="github_raw"`.
- Added platform-specific fetch paths:
  `fetch_huggingface_snapshot(...)` for dataset-to-JSONL snapshots and
  `fetch_github_raw_snapshot(...)` for raw-file byte snapshots.
- Kept the generic fetch dispatcher, staging directory workflow
  (`data/corpus/raw_staging/` -> `data/corpus/raw/`), per-source folder
  layout, and one `fetch_metadata.json` per source.
- Expanded the source registry with the RedLib v1 additions:
  `allenai/wildjailbreak`,
  `JailbreakBench/JBB-Behaviors` harmful behaviors,
  `walledai/MaliciousInstruct`,
  and the raw GitHub `AdvBench` file
  `data/advbench/harmful_behaviors.csv` from `llm-attacks/llm-attacks`.
- Preserved platform-native raw formats:
  Hugging Face snapshots continue to be written as JSONL records, while
  AdvBench is now saved as raw CSV bytes without semantic conversion.
- Extended fetch metadata so each snapshot records source platform,
  dataset identifier or URL, snapshot name, output file, fetch
  timestamp, record count where countable, and byte count.

Why this implementation was needed:
- RedLib's fetch stage needs to stay acquisition-only while still being
  flexible enough to absorb real corpus sources that are not all hosted
  behind one platform API.
- A declarative registry keeps new source additions mostly data-only
  rather than forcing fetch-loop rewrites.
- Preserving raw CSV for AdvBench keeps source fidelity intact for later
  audit and normalization stages, which is the right separation of
  concerns for this pipeline.

Conservative source-selection note:
- `JBB-Behaviors` exposes a clearly named harmful split, so only the
  harmful behaviors snapshot was added.
- `WildJailbreak` appears to expose `train` and `eval` configs rather
  than a clearly separate harmful-only split; those raw configs were
  snapshotted conservatively without row-level filtering at fetch time.
- RedLib should revisit `WildJailbreak` field and subset treatment
  during audit/normalization follow-up rather than pretending the fetch
  platform already exposes the exact final jailbreak-only slice.

Verification:
- Confirmed the refactor remains acquisition-only and does not invoke
  audit, normalization, classification, taxonomy discovery, ingestion,
  embeddings, Qdrant, or LLM calls.
- Attempted live fetch verification, but this shell session still does
  not have a usable Python interpreter and also cannot exercise network
  fetches here, so runtime execution could not be completed in-session.

---
## 2026-06-28
Implemented the third staged corpus-build script: `normalize_corpus.py`.

Issue:
- RedLib had acquisition and audit stages, but it still lacked the
  deterministic transformation step that turns raw heterogeneous
  snapshots into a clean, provenance-linked corpus for downstream
  taxonomy and ingestion work.
- Raw datasets use different prompt-bearing field names, and relying on
  heuristic field detection at normalization time would make downstream
  behavior brittle and non-deterministic.

Change:
- Added a new `normalize_corpus.py` that reads `data/corpus/raw/`,
  optionally loads `data/corpus/audit_report.json` as an engineering
  reference, and writes `data/corpus/normalized.jsonl`.
- Implemented explicit file-level prompt-field mappings for the current
  fetched sources instead of choosing fields heuristically at runtime:
  TrustAIRLab -> `prompt`, rubend18 -> `Prompt`,
  jackhhao -> `prompt`, and HarmBench HumanJailbreaks -> `Behavior`.
- Added conservative mechanical cleanup only:
  HTML entity decoding, line-ending normalization, invalid control
  character removal, trailing-horizontal-whitespace cleanup, repeated
  blank-line reduction, conservative internal repeated-space collapse,
  and final trim.
- Preserved provenance on every normalized record through:
  `source`, `source_file`, `source_row`, and a deterministic
  `prompt_id`.
- Preserved the original parsed raw record under `raw_fields` so later
  stages can trace every normalized prompt back to its source row
  without reopening normalization logic.
- Kept the stage strictly non-LLM, non-taxonomic, non-classifying, and
  non-ingesting.

Why this implementation was needed:
- Normalization is where RedLib needs a stable prompt text surface for
  later corpus-wide analysis, but it must do that without paraphrasing
  or altering semantic meaning.
- Explicit mappings prevent audit heuristics from silently becoming
  production field-selection rules.
- Stable provenance metadata and deterministic IDs make later taxonomy,
  classification, and embedding work traceable and reproducible across
  reruns.

Verification:
- Confirmed the implementation reads only raw JSONL snapshots, writes
  only `data/corpus/normalized.jsonl`, and does not create taxonomy,
  classified, or Qdrant artifacts.
- Attempted live script verification, but this shell session still does
  not have a usable Python interpreter available, so runtime execution
  could not be completed here.

---
## 2026-06-28
Implemented the second staged corpus-build script: `audit_corpus.py`.

Issue:
- The staged corpus pipeline now had an acquisition step
  (`fetch_corpus.py`), but it still lacked the read-only audit stage
  that measures raw corpus quality before any cleanup or taxonomy work.
- The raw snapshots intentionally preserve upstream schema differences
  and text artifacts, so RedLib needed a dedicated report that observes
  those conditions without mutating the source files.

Change:
- Added a new `audit_corpus.py` that reads only `data/corpus/raw/` and
  writes `data/corpus/audit_report.json`.
- Implemented corpus-level, source-level, file-level, and field-level
  summaries over raw JSONL snapshots.
- Added audit coverage for:
  total sources, total files, total records, per-source record counts,
  empty records, malformed JSONL lines, missing/null values by field,
  schema variation, duplicate raw records, duplicate likely prompt text,
  very short text fields, very long text fields, HTML entity indicators,
  escaped newline indicators, and suspicious control characters.
- Implemented statistical detection of likely prompt-bearing fields
  based on raw string coverage and length, while explicitly avoiding any
  canonical field choice or normalization decision.
- Made the script fail clearly if `data/corpus/raw/` does not exist, so
  the staged workflow remains explicit:
  fetch first, audit second.

Why this implementation was needed:
- Audit belongs between acquisition and normalization because RedLib
  needs to understand real upstream quality problems before choosing any
  cleanup rules.
- The report now gives later stages an observable baseline for schema
  drift, malformed lines, duplicates, and text-shape anomalies without
  silently rewriting the evidence.
- Keeping the audit strictly read-only preserves the single
  responsibility of this stage and prevents early normalization from
  leaking into raw corpus handling.

Verification:
- Confirmed the implementation reads raw `*.jsonl` files, writes only
  `data/corpus/audit_report.json`, and does not create normalized,
  taxonomy, classified, embedding, or Qdrant artifacts.
- Attempted live script verification, but this shell session still does
  not have a usable Python interpreter available, so runtime execution
  could not be completed here.

---
## 2026-06-28
Synchronized `CLAUDE.md` with current RedLib architecture.

Issue:
- `CLAUDE.md` contained obsolete Pinecone-era references, "nothing built
  yet" placeholders, and stale implementation notes that conflicted with
  the current Qdrant-backed, fully-implemented system described in
  `AGENTS.md` and `docs/ARCHITECTURE.md`.

Change:
- Replaced all Pinecone references with Qdrant Cloud.
- Updated tech stack section to reflect current implementation.
- Rewrote file structure to include all six corpus pipeline scripts
  (`fetch_corpus.py`, `audit_corpus.py`, `normalize_corpus.py`,
  `discover_taxonomy.py`, `classify_corpus.py`, `ingest.py`) and the
  organized `data/corpus/` directory structure.
- Updated pipeline stages section to describe the single corpus-grounded
  `RetrieverQueryEngine` path (no RouterQueryEngine, no conceptual bypass).
- Rewrote common task patterns to reflect the staged corpus workflow
  instead of direct dataset loading and ingestion.
- Updated "Current Project State" to reflect that the system is fully
  implemented and operational.
- Removed deployment-tier details (Vercel, Hetzner) that belong in
  infrastructure documentation, not coding-agent instructions.
- Preserved coding conventions, git commit format, and self-updating
  meta-instruction, which remain valid.

Why this synchronization was needed:
- `CLAUDE.md` is the active coding-agent instruction file. When it
  conflicts with the source of truth (`AGENTS.md`, `docs/ARCHITECTURE.md`),
  the agent may act on stale assumptions.
- The previous version assumed pre-implementation state and direct
  Pinecone integration. Claude acting on those instructions would propose
  changes to a system that no longer exists.

Result:
- `CLAUDE.md` now accurately reflects the current implemented system and
  can serve as the active instruction file for Claude during development
  sessions.

---

## 2026-06-28
Implemented the first staged corpus-build script: `fetch_corpus.py`.

Issue:
- The staged corpus pipeline was documented across `README.md`,
  `AGENTS.md`, and `docs/ARCHITECTURE.md`, but the actual first-stage
  acquisition script did not exist yet.
- The older dataset-loading path in `data_loader.py` mixed in
  downstream assumptions such as prompt-field extraction, filtering, and
  deduplication, which do not belong in the raw snapshot stage.

Change:
- Added a new `fetch_corpus.py` with an explicit dataset registry for
  the current HuggingFace sources:
  `TrustAIRLab/in-the-wild-jailbreak-prompts`,
  `rubend18/ChatGPT-Jailbreak-Prompts`,
  `jackhhao/jailbreak-classification`, and `swiss-ai/harmbench`.
- Implemented acquisition-only snapshotting into `data/corpus/raw/`,
  with one source-specific folder per dataset and JSONL artifacts per
  configured split/config.
- Preserved raw record shape by writing fetched records directly as
  JSONL rows without prompt extraction, cleaning, normalization,
  filtering, deduplication, or classification.
- Added per-source `fetch_metadata.json` files that record source name,
  dataset identifier, fetch timestamp, split/config, output filename,
  and record counts.
- Made the script safely rerunnable by fetching into
  `data/corpus/raw_staging/` first, then replacing the canonical
  `data/corpus/raw/` snapshot only after a successful full fetch.
- Added optional `HUGGINGFACE_TOKEN` support through the HuggingFace
  datasets client without making authentication mandatory for public
  sources.

Why this implementation was needed:
- RedLib's documented corpus workflow starts with reproducible local
  acquisition. Without a real fetch stage, there was no canonical raw
  corpus snapshot for later audit and normalization steps to inspect.
- Keeping raw source data untouched at this stage preserves upstream
  schema quirks and quality issues for `audit_corpus.py`, which is the
  correct place to inspect them.
- Atomic replacement-on-success avoids mixing old and new source files
  during reruns while still maintaining the single canonical raw corpus
  layout RedLib expects.

Verification:
- Confirmed the new implementation is isolated to `fetch_corpus.py` and
  does not touch retrieval, embeddings, Qdrant, Cohere, Anthropic, or
  LlamaIndex pipeline code.
- Attempted to run a syntax check and a network-free smoke test, but
  this shell session does not currently have a usable Python interpreter
  available, so live execution could not be completed here.

---
## 2026-06-28
Redesigned the documented corpus architecture around a staged local
pipeline.

Issue:
- The project documentation still described corpus preparation as a
  direct dataset-loading flow that moved too quickly from public dataset
  access into classification and ingestion.
- That design blurred several distinct engineering concerns:
  reproducible source snapshotting, corpus quality analysis,
  deterministic normalization, taxonomy design, taxonomy application,
  and final vector ingestion.

Decision:
- RedLib's documentation was intentionally redesigned to treat corpus
  building as a staged local pipeline:
  `fetch_corpus.py -> audit_corpus.py -> normalize_corpus.py ->
  discover_taxonomy.py -> classify_corpus.py -> ingest.py`.
- The new source of truth is a versioned local corpus under
  `data/corpus/`, where raw source data remains untouched and every
  downstream artifact has a single clear purpose.

Why this redesign was needed:
- Reproducibility: local raw snapshots make corpus versions auditable
  and repeatable.
- Data quality: auditing raw inputs before cleanup makes quality issues
  visible instead of silently absorbing them into ingestion.
- Determinism: normalization becomes a stable transformation rather than
  an ad hoc side effect of loading code.
- Taxonomy quality: prompt families should be discovered from the corpus
  first, then reviewed by humans before classification is applied across
  the dataset.
- Separation of concerns: ingestion should embed finalized classified
  artifacts, not serve as the place where corpus preparation decisions
  are made.

Documentation changes:
- Rewrote `docs/ARCHITECTURE.md` so the staged corpus pipeline is now
  the current architecture reference.
- Updated `README.md` to explain the high-level corpus workflow without
  implementation detail.
- Updated `AGENTS.md` so contributor guidance now treats each future
  corpus-stage script as a single-responsibility component.
- Updated `docs/CONTEXT.md` to replace fixed-taxonomy language with the
  new taxonomy philosophy: discovery, human review, then corpus-wide
  classification.

Result:
- Current-facing docs now describe only the staged corpus pipeline.
- The earlier direct-ingestion architecture is preserved here in
  `PROGRESS.md` as project history rather than in living documentation.

---
## 2026-06-28
Increased result-card prompt excerpts from ~300 to ~500 characters.

Issue:
- Search result cards were truncating prompt excerpts at roughly 300
  characters, which sometimes cut off useful context too early for
  scan-first review.
- The full prompt was still available through the explicit `View Full
  Prompt` workflow, but the feed itself could surface a bit more
  evidence without changing the API shape or inspection model.

Change:
- Updated `app.py` so `prompt_excerpt` now uses the first 500
  characters of the stored prompt text instead of the first 300.
- Kept the existing truncation behavior that avoids splitting the
  excerpt mid-word when a longer prompt is clipped.
- Left the full-prompt endpoint and modal workflow unchanged.

Why this was the correct fix:
- This is a small UI polish that improves card-level context while
  preserving RedLib's existing scan-friendly result design.
- Keeping the change in the backend excerpt builder means the frontend
  continues to render the same field and the API response schema does
  not change.

Verification:
- Verified in `app.py` that the only `prompt_excerpt` construction path
  now uses a shared `PROMPT_EXCERPT_CHARS = 500` constant.
- Verified the frontend still renders `result.prompt_excerpt` directly,
  so cards will receive the longer excerpt without any UI code changes.
- Attempted live HTTP verification against the local backend, but the
  endpoint did not respond during this session, so no runtime screenshot
  or API payload sample was captured here.

---
## 2026-06-28
Added lazy full-prompt fetching for explicit source inspection.

Issue:
- Search results only returned `prompt_excerpt`, which kept responses
  lightweight and safe, but the frontend still labeled the card action
  as `Detailed Report` and only showed the same truncated excerpt in the
  modal.
- That made result inspection misleading: users could not explicitly
  inspect the full retrieved prompt without bloating every search
  response or weakening the distinction between grounded AI summary and
  raw source material.

Change:
- Added `GET /api/prompts/{prompt_id}` in `app.py`.
- Implemented the endpoint as a direct Qdrant lookup that filters on the
  stored metadata field `prompt_id`, scrolls for exactly one record,
  reconstructs the stored `TextNode` from `_node_content`, and returns:
  `id`, `full_prompt`, `technique`, and `source`.
- Kept `POST /api/query` excerpt-based. Search responses still return
  only `prompt_excerpt` for result cards.
- Updated the frontend result-card action from `Detailed Report` to
  `View Full Prompt`, opened the modal immediately on click, showed a
  loading state while fetching, and rendered either the full prompt or a
  clear inline error message.
- Updated `docs/ARCHITECTURE.md` and `DESIGN.md` to document the new
  endpoint and the lazy inspection interaction.

Why this was needed:
- Lazy fetching is the right balance for RedLib. It preserves fast,
  scan-friendly result lists and avoids sending raw full prompts in
  every search response, while still allowing explicit source inspection
  after the responsible-use gate.
- It also keeps the AI summary constraints intact: synthesis still does
  not reproduce full prompts. Full prompt viewing is a separate,
  user-initiated inspection path.

Result:
- Search remains excerpt-based and lightweight.
- Full prompts are now available on demand through a dedicated backend
  endpoint and a correctly labeled frontend modal.

---
## 2026-06-28
Fixed category clicks so technique selection immediately loads results.

Issue:
- Clicking a visible technique in the sidebar updated the active visual
  state but did not load any results when the search box was empty.
- This made the category list feel broken even though the filters and
  counts themselves were rendering correctly.

Root cause:
- In `frontend/js/app.js`, the category click handler only called
  `handleSearch()` when `currentQuery` was already non-empty.
- `handleSearch()` also returned early if the search input was blank.
- As a result, category selection without a prior typed query never sent
  a request to `/api/query`.

Change:
- Updated `handleSearch()` so it uses the active category name as a
  fallback query when the search box is empty.
- Updated the category toggle path so clicking a category triggers
  search whenever either a text query or an active category can drive
  the request.

Why this was the correct fix:
- Category clicks are a first-class navigation action, so they should
  produce corpus-grounded results even without a typed free-text query.
- Using the category name itself as the fallback query preserves the
  existing `/api/query` contract and keeps the search corpus-grounded.

Verification:
- Direct backend verification confirmed category-filtered requests work,
  for example:
  `{"query":"Fictional Framing","category_filter":"Fictional Framing"}`
  returns five filtered results.
- The frontend click flow now reaches that same backend path when the
  user selects a category with an empty search box.
- Normal typed searches still work, and typed queries continue to
  combine with an active category filter when one is selected.

---
## 2026-06-28
Improved sidebar technique loading so labels appear immediately and
counts hydrate asynchronously.

Issue:
- The sidebar technique list stayed blank until `/api/categories`
  completed, which made the search page feel empty on first load.
- After the live-count backend fix, `/api/categories` could take
  noticeably longer because it computed counts from Qdrant rather than
  returning placeholders.
- Zero-count techniques also remained visible, which created dead-end
  filters that added noise without helping corpus navigation.

Root cause:
- `frontend/js/app.js` waited for `/api/categories` before rendering any
  technique rows, so there was no immediate scaffold for the sidebar.
- The backend category endpoint was doing live work on every request,
  which made repeated page loads slower than necessary.

Change:
- Added a frontend constant for the ten known RedLib techniques and
  their icons.
- The sidebar now renders those labels immediately on page load with
  count badges showing `...` while live counts are loading.
- When `/api/categories` returns, the frontend merges the live counts
  into the existing technique list and re-renders it.
- Techniques with `count === 0` are removed after counts are known, so
  only useful corpus filters remain visible.
- Preserved the current filter interaction by keeping the same category
  names and row click behavior.
- Added a lightweight backend cache for category counts in `app.py`, so
  the first request computes live totals and subsequent requests reuse
  them for a short TTL instead of rescanning Qdrant every time.

Why this was the correct fix:
- The technique list is navigational structure, so its labels should be
  available immediately even before telemetry-style count data finishes
  loading.
- Count hydration belongs on top of a stable known taxonomy, not as a
  prerequisite for rendering the sidebar at all.
- Hiding zero-count categories after load keeps the filter list focused
  without changing the underlying corpus model or query behavior.

Verification:
- `/api/categories` still returns the same response schema and live
  counts.
- Category-filtered `POST /api/query` requests still succeed, confirming
  that sidebar filter behavior remains intact.
- Repeated `/api/categories` requests showed the cache working in
  practice: the first call took roughly `18813ms`, while the second
  completed in roughly `44ms`.
- The frontend now has immediate technique labels, loading-state badges,
  and post-load zero-count hiding in the rendering path.

---
## 2026-06-28
Replaced hardcoded zero sidebar counters with live technique totals.

Issue:
- The left sidebar technique counters all displayed `0`, which made the
  corpus navigation controls look empty even though Qdrant contained
  thousands of prompts.
- Frontend tracing showed `frontend/js/app.js` already fetched
  `/api/categories` and rendered whatever `count` values the backend
  returned. The problem was upstream: `app.py` returned a hardcoded
  category list with zero counts.

Root cause:
- `GET /api/categories` in `app.py` was still a Phase 1 placeholder that
  returned the ten technique names with static `count: 0`.
- While implementing a live backend count path, a second compatibility
  issue surfaced: this Qdrant collection does not have a keyword payload
  index on `technique`, so direct filtered count requests fail with
  `Index required but not found for "technique"`.
- The same missing index also affected the existing category-filtered
  search path, and `app.py` was additionally trying to pass
  `filters=...` into `query_engine.query(...)`, which the installed
  LlamaIndex `BaseQueryEngine` does not accept.

Change:
- Replaced the hardcoded category response with a live aggregation helper
  in `app.py` that scrolls the Qdrant payloads and counts prompts by
  `technique` in-process. This keeps `/api/categories` live without
  requiring re-ingestion or a new schema migration.
- Added a reusable keyword-index helper for Qdrant-filtered fields.
- Preserved category filtering by applying the selected
  `MetadataFilters` directly to the active underlying retrievers before
  query execution, then restoring the original retriever state after the
  request completes.

Why this was the correct fix:
- The sidebar counters are corpus-navigation metadata, so they should be
  sourced from the live corpus, not from current search-result counts or
  placeholder values.
- Using scroll-based aggregation avoids turning this UI bug into a
  mandatory re-indexing task.
- The frontend design and rendering path were already correct, so the
  smallest fix was entirely backend-side.

Verification:
- `GET /api/categories` now returns live counts, for example:
  `Persona Hijacking=2254`, `Fictional Framing=330`,
  `Instruction Injection=755`.
- The frontend rendering path remained unchanged and now has non-zero
  values to display.
- `POST /api/query` with
  `{"query":"persona hijack","category_filter":"Persona Hijacking"}`
  succeeds and still returns filtered results, confirming that the
  sidebar filter workflow remains intact.

---
## 2026-06-28
Fixed an unintended two-result cap in the active retrieval pipeline.

Issue:
- Searches were only returning two prompt cards in the UI, even though
  `retriever.py` configured dense and sparse retrieval with `top_k=20`
  and the frontend rendered every result the API returned.
- Investigation showed the active backend path was:
  `QueryFusionRetriever` -> `CohereRerank` -> `RetrieverQueryEngine` ->
  `/api/query`, and the API itself was already returning only two
  results.

Root cause:
- `retriever.py` passed `top_k=20` into the dense and sparse
  sub-retrievers, but did not pass `similarity_top_k` into
  `QueryFusionRetriever`.
- In the installed LlamaIndex version, `QueryFusionRetriever` defaults
  `similarity_top_k` to `DEFAULT_SIMILARITY_TOP_K`, and that constant is
  `2`.
- That meant the fusion layer was clipping the merged result set to two
  nodes before Cohere reranking ever ran, so the intended `top_n=5`
  reranker cap never had a chance to apply.

Change:
- Updated `retriever.py` so `QueryFusionRetriever` now receives
  `similarity_top_k=top_k`.

Why this was the correct fix:
- The intended flow is:
  dense 20 + sparse 20 -> fusion keeps 20 -> Cohere rerank keeps 5 ->
  API returns up to 5 cards.
- `CohereRerank(top_n=5)` remains the correct final cap because it is
  the deliberate post-fusion ranking stage. The bug was the accidental
  earlier cap at fusion, not the reranker.

Verification:
- Queried the live backend with:
  `{"query":"persona hijack","category_filter":null}`
- Before the fix, `/api/query` returned `result_count=2`.
- After the fix, `/api/query` returned `result_count=5` and five result
  cards, confirming that the API and frontend now surface the full
  reranked set.

---

## 2026-06-28
Removed the direct conceptual query route so all answers are grounded in
the RedLib corpus.

Issue:
- The previous router design split queries into a corpus-backed
  `semantic_search` tool and a direct `conceptual_qa` tool with
  `retriever=None`.
- That made RedLib behave partly like a general chatbot instead of a
  corpus-grounded research assistant, and it also introduced a brittle
  failure mode where conceptual traffic could hit
  `'NoneType' object has no attribute 'retrieve'`.

Change:
- Replaced the two-route `RouterQueryEngine` setup with a single
  `RetrieverQueryEngine` built in `router.py`.
- Removed the direct `conceptual_qa` path entirely. All user queries now
  flow through the same Qdrant-backed retrieval stack:
  `QueryFusionRetriever` -> RRF -> `CohereRerank` -> Claude Haiku
  synthesis.
- Updated `rag.py` to assemble the simpler single-engine pipeline
  instead of building router tools and a selector.
- Updated `app.py` so `POST /api/query` now describes the endpoint as
  corpus-grounded and returns `query_type="semantic"` consistently.
- Updated `docs/ARCHITECTURE.md` and `docs/CONTEXT.md` to remove the old
  conceptual-bypass description and document the new retrieval-first
  behavior.

Why this was needed:
- This was an intentional architecture change, not just a compatibility
  patch. RedLib's value is grounded analysis of real jailbreak prompts,
  so even definition-style questions like "What is persona hijacking?"
  should be answered from retrieved corpus evidence instead of Claude's
  standalone prior knowledge.
- Removing the `None` retriever path also simplified the pipeline and
  eliminated a class of startup and query-time errors.

Result:
- All queries are now corpus-grounded, retrieved source nodes still flow
  into the API response, and the synthesis constraints remain in place:
  no full prompt reproduction, no execution-level jailbreak guidance,
  and grounded summaries only.

---

## 2026-06-28
Aligned router tool metadata with the installed LlamaIndex version.

Issue:
- Query-time routing was failing in `router.py` with
  `ValueError: Unexpected type: <class 'dict'>` because
  `QueryEngineTool` metadata for `semantic_search` and `conceptual_qa`
  was still being passed as plain dictionaries.

Change:
- Updated `router.py` to import the installed LlamaIndex
  `ToolMetadata` type alongside `QueryEngineTool`.
- Replaced both raw metadata dictionaries with structured
  `ToolMetadata(name=..., description=...)` objects while preserving the
  existing tool names and descriptions.
- Kept the rest of the router behavior unchanged:
  `LLMSingleSelector` still drives `RouterQueryEngine`, the semantic
  route still uses `RetrieverQueryEngine` with the retriever, Cohere
  reranker, and synthesizer, and the conceptual route remains the same.

Why this was needed:
- This was a compatibility fix for the installed LlamaIndex tool API,
  not a routing redesign. The documented architecture remained correct,
  but the router implementation was still using an older metadata shape
  that the current `QueryEngineTool` constructor no longer accepts.

Result:
- Frontend searches and `POST /api/query` should now progress past the
  previous router metadata type error without changing retrieval,
  synthesis, or response-shape behavior.

---

## 2026-06-28
Replaced stale hardcoded API stats with a live Qdrant-backed count.

Issue:
- `GET /api/stats` was still returning a hardcoded
  `total_prompts=2500`, which no longer matched the live `redlib`
  collection and caused the frontend stats bar to drift from the actual
  corpus size.
- The route also still referenced the old Pinecone-era plan in comments,
  even though the backend now uses Qdrant Cloud.

Change:
- Updated `app.py` so `/api/stats` creates a lightweight `QdrantClient`
  using the same `QDRANT_URL` and `QDRANT_API_KEY` environment-variable
  pattern used elsewhere in the project.
- Replaced the hardcoded prompt total with a live
  `QdrantClient.count(collection_name="redlib", exact=True)` lookup.
- Kept the existing response shape unchanged:
  `total_prompts`, `total_sources`, and `last_sync`.
- Left `total_sources=4` static for now because the configured source
  list is stable.
- Updated `docs/ARCHITECTURE.md` to describe the live Qdrant-backed
  stats behavior and to note that `app.py` now reads the Qdrant
  connection variables directly.

Why this was needed:
- This was a correctness fix for backend API data, not an architectural
  retrieval change. The app already depended on Qdrant for search, so
  reading the collection point count directly was the right way to avoid
  stale fake totals.
- The endpoint now fails clearly if the Qdrant lookup fails instead of
  silently returning outdated numbers.

Result:
- `/api/stats` now reports the live prompt count from the `redlib`
  collection while preserving the existing JSON shape consumed by the
  frontend.

---

## 2026-06-28
Aligned the synthesizer prompt wiring with the installed LlamaIndex version.

Issue:
- Backend startup was failing in `synthesizer.py` because
  `get_response_synthesizer(...)` was called with `system_prompt=...`,
  but the installed LlamaIndex 0.14.22 factory no longer accepts that
  keyword argument.

Change:
- Updated `synthesizer.py` to preserve the existing RedLib synthesis
  constraints by moving the live `SYSTEM_PROMPT` into supported
  `PromptTemplate` objects.
- Wired those templates into `get_response_synthesizer(...)` through
  `text_qa_template` and `refine_template`, which are supported by the
  installed API surface.
- Kept Claude Haiku 4.5 as the synthesis model and kept compact response
  mode unchanged.

Why this was needed:
- This was a compatibility fix, not a synthesis-policy change. The
  documented behavior in `docs/CONTEXT.md` remained correct, but the
  implementation was still using an older prompt-injection pattern that
  no longer matches the installed LlamaIndex factory signature.
- Compact mode in this version uses both an initial QA prompt and a
  refine prompt, so the constraints needed to be preserved in both
  templates rather than only on the first pass.

Result:
- Backend initialization should now progress past the previous
  `unexpected keyword argument 'system_prompt'` failure while preserving
  RedLib's grounded, compact, non-reproductive answer constraints.

---

## 2026-06-28
Aligned retriever construction with the installed LlamaIndex version.

Issue:
- Backend startup was failing during retriever initialization because
  `retriever.py` called `QdrantVectorStore.as_retriever(...)`, but the
  installed LlamaIndex build does not expose that method on the Qdrant
  vector store implementation.

Change:
- Updated `retriever.py` to keep building the `QdrantVectorStore` and
  `VectorStoreIndex` exactly as before, but route the sparse retriever
  through `VectorStoreIndex.as_retriever(...)` instead of calling the
  missing method on the vector store object.
- Preserved the documented retrieval flow:
  dense search + sparse search -> RRF via `QueryFusionRetriever` ->
  Cohere rerank -> Claude synthesis.
- Preserved the existing Qdrant collection name, hybrid-enabled vector
  store configuration, metadata filtering support, reranking model, and
  embedding model.

Why this was needed:
- This was a version-compatibility fix, not an architectural change.
  The documented retrieval design was still correct, but one of the
  construction patterns in the implementation was ahead of the installed
  LlamaIndex API surface.

Result:
- Backend initialization should now progress past the previous
  `'QdrantVectorStore' object has no attribute 'as_retriever'` failure
  without changing ingestion, query flow, or API response behavior.

---

## 2026-06-26
Repository-wide documentation synchronized with the current implementation,
and the ingestion pipeline debugging work was documented end-to-end.

Documentation:
- Adopted a clearer split between living documentation and historical
  progress. AGENTS.md, docs/ARCHITECTURE.md, README.md, and .env.example
  were updated to describe the repository as it exists today, while
  PROGRESS.md remains the place to preserve the engineering history.
- Removed obsolete Pinecone-era references from current-facing docs and
  replaced them with the active Qdrant implementation.
- Updated AGENTS.md to reflect the implemented Qdrant-backed pipeline,
  current ingestion safeguards, and the current repository layout.
- Updated docs/ARCHITECTURE.md to describe the live Qdrant collection
  schema, checkpoint-based ingestion flow, current metadata shape, and
  the fact that prompt text now lives in the TextNode body instead of
  metadata.
- Rewrote README.md for new contributors and users so it now explains
  the current project purpose, high-level pipeline, setup flow,
  ingestion workflow, and local run path without duplicating the
  architecture doc.
- Updated .env.example to match only the variables actually read by the
  current codebase: QDRANT_URL, QDRANT_API_KEY, OPENAI_API_KEY,
  ANTHROPIC_API_KEY, COHERE_API_KEY, and HUGGINGFACE_TOKEN.

Ingestion debugging journey:
- Investigated ingestion stopping around the first ~400 vectors already
  present in Qdrant. Dataset loading, classification, and embedding
  initialization were succeeding, so attention shifted to the handoff
  between LlamaIndex and Qdrant during the first insert_nodes() call.
- Diagnosed the first failure as a Qdrant upload timeout:
  httpcore.WriteTimeout -> httpx.WriteTimeout ->
  qdrant_client.http.exceptions.ResponseHandlingException.
  The immediate fix was to increase the Qdrant client timeout so larger
  upsert batches had enough time to complete over the network.
- Added insertion diagnostics around every index.insert_nodes(nodes) call:
  log before insert, log after successful insert, and log exception type,
  message, and batch size on failure. This made it possible to confirm
  the actual batch size being sent when the timeout occurred.
- Once Qdrant insertion began progressing again and the collection grew
  past the earlier ~400-point stall, ingestion exposed a second problem:
  OpenAI embedding failures on individual oversized prompts.
- The first oversize guard was based on character count. That prevented
  obviously large records from crashing the run, but it did not explain
  why some prompts with seemingly safe raw counts were still rejected by
  the embedding API.
- Added token counting with tiktoken and logged prompt_id, source,
  character count, and token count for each record. This improved
  observability, but the first token-based check still underestimated
  some requests.
- Investigated how LlamaIndex actually constructs embedding input and
  confirmed that it embeds node.get_content(metadata_mode=MetadataMode.EMBED),
  not just the raw record["text"] string.
- Added diagnostics for both values: token count of the raw record text
  and token count of the exact string returned by the TextNode for the
  embedding path. This exposed a mismatch between the string being
  measured and the string actually sent to OpenAI.
- Root cause: each TextNode was created with prompt text in both places:
  TextNode.text and metadata["text"]. When LlamaIndex built the EMBED
  content, it prepended metadata to the node body, causing the full
  prompt to be duplicated in the embedding request.
- Applied the architectural fix instead of only adding more defensive
  skipping: removed duplicated prompt text from metadata and kept only
  true metadata fields (source, technique, prompt_id). The prompt itself
  remains stored in the TextNode body for retrieval and synthesis.
- Updated app.py to continue retrieving prompt text from the node body
  via node.get_content(metadata_mode=MetadataMode.NONE) rather than from
  metadata. That keeps result excerpts aligned with the corrected node
  schema.
- Retained the token-limit guard as a safety mechanism for genuinely
  oversized prompts, but it now checks the exact content that will be
  embedded rather than guessing from raw characters alone.

Lessons learned:
- Validate the exact object being sent to an external API, not just the
  source value that seems closest upstream.
- Avoid duplicating large content in metadata, especially when framework
  helpers may merge metadata back into model inputs.
- Prefer fixing architectural causes over stacking defensive workarounds.
- Keep living documentation focused on the current system, and preserve
  engineering history separately in PROGRESS.md.

Result:
- Ingestion debugging is now captured as a coherent engineering narrative
  instead of scattered point fixes.
- Current-facing documentation reflects the live Qdrant-based system,
  while PROGRESS.md preserves how the project got there.

---
## 2026-06-28
Added a Qdrant payload index for `prompt_id` so full-prompt lookup works
against both new and already-populated collections.

Issue:
- `GET /api/prompts/{prompt_id}` was implemented as a direct Qdrant
  payload filter on the metadata field `prompt_id`.
- Qdrant rejected that lookup on the live `redlib` collection with:
  `Index required but not found for "prompt_id" of type [keyword]`.
- The endpoint design was correct, but the collection needed an
  explicit keyword payload index before that metadata field could be
  used reliably for filtered lookup.

Change:
- Updated `ingest.py` to ensure a Qdrant keyword payload index exists on
  `prompt_id` after the collection is created or reused, before any
  upsert work begins.
- Added a lightweight safeguard in `app.py` so the API checks for the
  `prompt_id` payload index and creates it lazily if the backend is
  pointed at an older live collection that predates the ingestion-side
  fix.
- Updated `docs/ARCHITECTURE.md` to document `prompt_id` as an indexed
  payload field used by `GET /api/prompts/{prompt_id}`.

Why this was needed:
- This fixes the actual Qdrant requirement instead of forcing a full
  re-ingestion or redesigning prompt lookup around a different ID path.
- Creating the payload index is safe for an existing collection and
  keeps the current node schema intact: prompt text still lives in the
  `TextNode` body, metadata still stores only `source`, `technique`, and
  `prompt_id`, and the retrieval pipeline remains unchanged.

Result:
- New collections created through `ingest.py` now provision the payload
  index automatically.
- Existing live collections can be upgraded in place by the backend on
  first prompt lookup.
- The full-prompt endpoint no longer depends on re-ingestion just to
  make metadata filtering work.

---
## 2026-07-07
Implemented `classify_corpus.py` as the corpus-wide taxonomy
application stage.

Issue:
- The staged corpus pipeline already had normalized prompt preparation
  and hierarchical taxonomy discovery, but it still lacked the
  operational stage that applies the approved taxonomy across every
  normalized prompt and produces the final classified corpus artifact.
- The repository also still contained older fixed-label classification
  logic in `classifier.py` and `ingest.py` that does not match the
  newer taxonomy-first architecture or the richer classification output
  shape needed for auditability.

Change:
- Added a new `classify_corpus.py` that reads
  `data/corpus/normalized.jsonl` plus
  `data/corpus/proposed_taxonomy.json` and writes
  `data/corpus/classified.jsonl`.
- Implemented Anthropic schema-backed structured outputs via
  `client.messages.parse(..., output_format=BatchClassificationOutput)`
  instead of free-form JSON parsing.
- Enforced one dominant primary category per prompt, optional approved
  subtechnique, controlled supporting traits, confidence, and short
  rationale, with a code-defined fallback category
  `Unclear / Needs Review` when classification cannot be validated.
- Added resume-safe checkpointing, append-only staging writes,
  incremental progress persistence, retry accounting, failure logging,
  structured-output debug artifacts, and recursive batch splitting when
  token estimates or repeated failures make a full batch unsafe.
- Kept provenance intact by preserving every normalized record field in
  the final output and only appending the nested `classification`
  object.
- Updated `docs/ARCHITECTURE.md` to document the final
  `classified.jsonl` record shape and updated `AGENTS.md` current-state
  notes to reflect the implemented stage.

Why this implementation was needed:
- Classification is a distinct stage boundary in RedLib's corpus design:
  taxonomy discovery proposes the label system, while classification
  applies that approved system consistently at full-corpus scale.
- Given the corpus size, interruption-safe staging and checkpointing
  are not optional implementation details; they are required to make the
  stage practical and auditable.
- Using structured outputs keeps category/subtechnique control in the
  approved taxonomy instead of relying on free-form label generation.

Verification:
- Confirmed the new script validates normalized and taxonomy inputs,
  streams normalized records in batches, and writes only staging/final
  classified artifacts plus checkpoint/debug sidecars.
- Basic runtime verification is limited to static validation in-session;
  a live end-to-end classification run still depends on Doppler-managed
  Anthropic credentials and network access at execution time.

---
## 2026-07-07
Removed AdvBench from the active corpus pipeline and clarified RedLib's
corpus scope as adversarial jailbreak prompts only.

Issue:
- The live pipeline still fetched and normalized AdvBench even though
  RedLib's current architecture and taxonomy work are centered on
  adversarial prompts that manipulate or bypass LLM safety behavior.
- That created a scope mismatch: pure harmful requests without a
  jailbreak mechanism could enter the corpus even though they do not fit
  the intended mechanism-focused taxonomy surface.

Change:
- Removed the AdvBench source from `fetch_corpus.py` so future raw
  corpus snapshots no longer download or stage that dataset.
- Deleted the now-dead AdvBench prompt-field mapping from
  `normalize_corpus.py`.
- Updated `README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, and
  `docs/CONTEXT.md` to state explicitly that RedLib is a corpus of
  adversarial jailbreak prompts designed to manipulate, override, or
  bypass LLM safety behavior.
- Documented the exclusion explicitly: direct harmful requests without a
  jailbreak mechanism are out of scope for future corpus rebuilds.

Why this implementation was needed:
- RedLib's taxonomy is intended to describe jailbreak mechanisms, not to
  absorb generic harmful-intent requests as a parallel class of prompt.
- Removing AdvBench from acquisition is the cleanest way to keep future
  corpus rebuilds aligned with the documented scope without introducing
  extra semantic filtering logic into later stages.

Verification:
- Confirmed AdvBench was removed from the live fetch registry and from
  normalization field mappings.
- Verified current-facing documentation now describes the corpus as
  adversarial jailbreak prompts only.
- Existing local corpus artifacts were left untouched as intended; the
  next full rebuild will naturally regenerate downstream artifacts
  without AdvBench.

---
## 2026-07-07
Reduced classification retry churn by tightening rationale instructions
instead of relying on repeated batch retries.

Issue:
- `classify_corpus.py` was repeatedly retrying and recursively splitting
  otherwise-correct batches because Claude often returned rationale
  strings that were longer than the intended structured-output shape.
- The dominant classification decision was usually correct; the failure
  mode was mostly rationale verbosity, which wasted API calls and slowed
  full-corpus classification substantially.

Change:
- Tightened the classification system prompt so rationale is explicitly
  constrained to one concise sentence, objective language, 120
  characters or fewer, the dominant decision only, and no extra
  justification or discussion.
- Tightened the user-visible batch prompt with the same rationale rules
  so the output contract is reinforced in both prompt layers.
- Increased the schema ceiling for `rationale` modestly to `300`
  characters so small structured-output variance can pass without
  encouraging long explanations.
- Removed the silent Python-side `rationale[:240]` truncation so
  overlong model output now fails transparently through structured
  validation instead of being masked after parsing.

Why this implementation was needed:
- The retry and recursive split machinery should be reserved for genuine
  request failures, not triggered routinely by verbose one-field model
  output.
- Tightening the prompt contract is the right fix because the
  classification content was already mostly correct; the system mainly
  needed a clearer rationale budget.

Verification:
- Confirmed structured outputs remain active through
  `client.messages.parse(..., output_format=BatchClassificationOutput)`.
- Confirmed Pydantic validation still governs `rationale`, now with a
  modestly wider schema cap and no silent truncation path in Python.
- Live 100-record smoke-test verification remains blocked in this shell
  because no usable Python launcher is available.
