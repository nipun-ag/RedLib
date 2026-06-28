# RedLib — Progress Log

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
