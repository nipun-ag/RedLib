# RedLib — Progress Log

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
