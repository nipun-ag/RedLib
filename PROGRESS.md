# RedLib — Progress Log

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
