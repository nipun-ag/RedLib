# RedLib - Architecture

## Overview
RedLib has two major systems:

1. A staged local corpus pipeline that turns public jailbreak datasets
   into a reproducible, normalized, human-reviewed classified corpus.
2. A query pipeline that indexes that finalized corpus in Qdrant Cloud
   and serves corpus-grounded retrieval and synthesis through FastAPI.

RedLib's corpus scope is adversarial jailbreak prompts only: prompts
that manipulate, override, or bypass LLM safety behavior. Pure harmful
requests without a jailbreak mechanism are out of scope.

Frontend assets live under `frontend/` as static HTML/CSS/JS.

---

## Architecture Principles

- Raw source data is preserved exactly as downloaded.
- Corpus versions are reproducible and locally inspectable.
- Every corpus stage has exactly one responsibility.
- Corpus scope is restricted to adversarial jailbreak prompts rather
  than direct harmful requests with no jailbreak mechanism.
- Normalization is deterministic and separate from classification.
- Taxonomy is discovered from the corpus first, then approved by humans
  before it is applied at scale.
- Ingestion is the last step, not the place where corpus design happens.

---

## File / Folder Structure

```text
redlib/
|- api/
|  |- __init__.py
|  |- app.py                  # FastAPI app entry point. All API routes.
|  |- rag.py                  # Assembles the full LlamaIndex query pipeline.
|  |- embedder.py             # Configures OpenAI text-embedding-3-small.
|  |- retriever.py            # Configures Qdrant hybrid retrieval and Cohere rerank.
|  |- router.py               # Builds the corpus-grounded RetrieverQueryEngine.
|  `- synthesizer.py          # Configures response synthesis with Claude Haiku 4.5.
|- corpus/
|  |- __init__.py
|  |- fetch_corpus.py         # Snapshots public datasets and raw source files into local corpus storage.
|  |- convert_sources.py      # Converts raw source formats into canonical JSONL records.
|  |- audit_corpus.py         # Analyzes canonical corpus quality without modifying it.
|  |- normalize_corpus.py     # Deterministically normalizes prompt records from canonical JSONL.
|  |- corpus_sampling.py      # Shared deterministic sampling helpers for discovery and experiments.
|  |- discover_taxonomy.py    # Derives candidate prompt families from normalized data.
|  |- classify_corpus.py      # Applies the approved taxonomy across the corpus.
|  `- ingest.py               # Embeds finalized classified corpus into Qdrant.
|- data/
|  `- corpus/
|     |- raw/                 # Immutable source dataset snapshots
|     |- canonical/           # Canonical JSONL records with full provenance
|     |- audit_report.json    # Structured corpus quality report
|     |- normalized.jsonl     # Deterministically normalized corpus
|     |- proposed_taxonomy.json # Iterative human-review taxonomy proposal
|     |- classified.jsonl     # Final corpus handed to ingestion
|     `- classified_with_subtechniques.jsonl
|                            # Archive copy with subtechniques preserved
|- frontend/                  # Static frontend assets
|  |- index.html
|  |- search.html
|  |- css/
|  |  `- style.css
|  `- js/
|     |- config.js
|     `- app.js
|- docs/
|  |- ARCHITECTURE.md         # This file
|  |- CONTEXT.md              # Synthesis prompt rules and taxonomy philosophy
|  |- DESIGN.md               # Design system and UI guidance
|  `- PROGRESS.md             # Historical engineering log
|- requirements.txt
|- .env.example
|- .gitignore
|- AGENTS.md
`- README.md
```

---

## Corpus Pipeline

### Stage Sequence

```text
Public Datasets
      -> python -m corpus.fetch_corpus
      -> data/corpus/raw/
      -> python -m corpus.convert_sources
      -> data/corpus/canonical/
      -> python -m corpus.audit_corpus
      -> data/corpus/audit_report.json
      -> python -m corpus.normalize_corpus
      -> data/corpus/normalized.jsonl
      -> python -m corpus.discover_taxonomy
      -> data/corpus/proposed_taxonomy.json
      -> human review
      -> python -m corpus.classify_corpus
      -> data/corpus/classified.jsonl
      -> python -m corpus.ingest
      -> Qdrant
```

### Why The Pipeline Is Staged

- `corpus.fetch_corpus` exists so dataset acquisition is reproducible
  and separated from every downstream transformation.
- `corpus.convert_sources` exists so downstream stages never need to
  know whether an upstream source arrived as JSONL, CSV, or another
  platform-native format.
- `corpus.audit_corpus` exists so quality problems are measured before
  cleanup rules are chosen, rather than hidden by eager mutation.
- `corpus.normalize_corpus` exists so ingestion receives a stable
  prompt format and corpus cleanup stays deterministic after the prompt
  field has already been selected.
- `corpus.discover_taxonomy` exists so RedLib's labels emerge from the
  data instead of being permanently hardcoded up front.
- `corpus.classify_corpus` exists so taxonomy application is
  consistent, corpus-wide, and auditable as a separate operation.
- `corpus.ingest` exists only to embed and index the finalized corpus,
  not to make corpus-preparation decisions.

---

## Corpus Artifacts

### `data/corpus/raw/`
- Immutable local snapshot of every source dataset
- Source of truth for reproducible corpus builds
- Never edited in place

### `data/corpus/canonical/`
- Canonical JSONL conversion of every supported raw source file
- Downstream input for audit and normalization
- Preserves `source`, `source_file`, `source_row`, and all original
  source fields under `fields`

### `audit_report.json`
- Structured report of canonical-corpus quality issues
- Used to drive engineering decisions about normalization and source handling
- Does not contain cleanup logic

### `normalized.jsonl`
- Deterministically cleaned prompt records
- Consistent input format for taxonomy discovery
- Free of source-specific encoding and formatting noise
- Built from explicit source/file field mappings rather than heuristic
  or semantic filtering
- Scoped to adversarial jailbreak prompts rather than pure harmful
  requests with no jailbreak mechanism

### `proposed_taxonomy.json`
- Iterative taxonomy proposal derived from the normalized corpus
- Stores a hierarchical taxonomy with broad top-level mechanism
  families and supporting subtechniques
- Records sampling strategy, iteration history, and saturation status
- Uses code-computed support counts and source distribution from cited
  analyzed samples rather than model-invented numbers
- Intended for human review before it becomes operational taxonomy

### `classified.jsonl`
- Final classified corpus with 168,117 confirmed records
- Preserves normalized-record provenance and raw source fields
- Stores one dominant primary jailbreak mechanism per prompt plus
  supporting traits, confidence, and a short rationale
- Subtechnique field removed from every classification object
- Produced by `python -m corpus.classify_corpus`
- Consumed by `python -m corpus.ingest`

### `classified_with_subtechniques.jsonl`
- Archive copy of the classified corpus with subtechnique preserved
- Retained for future reference only
- Not consumed by the pipeline

Classified record shape:
```json
{
  "prompt_id": "string",
  "source": "string",
  "source_file": "string",
  "source_row": 0,
  "text": "string",
  "raw_fields": {},
  "classification": {
    "primary_category": "string",
    "supporting_traits": ["string"],
    "confidence": 0.0,
    "rationale": "string"
  }
}
```

### Operational Sidecars

### `classified_staging.jsonl`
- Staging file written during `python -m corpus.classify_corpus` runs
- Atomically replaces `classified.jsonl` on successful completion

### `classified_checkpoint.json`
- Checkpoint tracking classification progress for resume support

### `ingest_checkpoint.json`
- Checkpoint written by `python -m corpus.ingest` after each successful batch
- Stores `last_ingested_prompt_id`, `records_ingested`, `total_records`, and `timestamp`
- Used to resume ingestion from the next classified record after interruption

### `ingest_oversized.jsonl`
- Append-only quarantine file written by `python -m corpus.ingest`
- Stores the full classified record plus a `token_count` field for any record whose embedding content exceeds the ingestion safety limit
- Oversized records are logged and checkpointed as processed so they do not repeatedly retry on resume runs

### `classification_failures.jsonl`
- Per-batch failure log written during `python -m corpus.classify_corpus` runs

### `classification_debug/`
- Debug payloads written on structured output failures during classification

### `taxonomy_debug/`
- Debug payloads written on structured output failures during taxonomy discovery

### `experiments/`
- Isolated experiment outputs from `python -m corpus.classify_corpus` experiment mode
- Never consumed by `python -m corpus.ingest`

### `experiments/samples/`
- Reusable stratified sample files generated by `corpus/corpus_sampling.py`
- Used for experiment runs

### `raw/fetch_run_summary.json`
- Run-level summary written by `python -m corpus.fetch_corpus` after each acquisition run

### `raw/<source>/fetch_metadata.json`
- Per-source acquisition metadata written by `python -m corpus.fetch_corpus`

---

## Query-Time Architecture

The query path remains corpus-grounded end to end:

```text
User query (POST /api/query)
      -> api.app
Build single RetrieverQueryEngine
      -> api.router
Dense + sparse retrieval from Qdrant
      -> QueryFusionRetriever
Reciprocal rank fusion
      -> CohereRerank
Top reranked nodes
      -> api.synthesizer
Claude Haiku grounded synthesis
      -> api.app
Assemble answer + result cards + technique breakdown
      ->
JSON response to frontend
```

All user queries go through the same retrieval path. There is no direct
LLM-only conceptual route.

---

## API Endpoints

### POST /api/query
Main RAG query endpoint.

Request:
```json
{
  "query": "string",
  "category_filter": "string | null"
}
```

Response:
```json
{
  "answer": "string",
  "results": [
    {
      "id": "string",
      "prompt_excerpt": "string",
      "technique": "string",
      "source": "string",
      "confidence": "HIGH | MED | LOW",
      "confidence_score": 0.0
    }
  ],
  "technique_breakdown": {
    "Example Category": 0
  },
  "result_count": 0,
  "query_type": "semantic"
}
```

Implementation details:
- `category_filter` is applied as a metadata filter on `technique`
- `prompt_excerpt` is built from the node body, not from metadata
- `query_type` is always `"semantic"` because all queries use the same
  corpus-grounded retrieval path

### GET /api/categories
Returns the approved taxonomy categories and live corpus counts used by
the frontend filter sidebar.

### GET /api/prompts/{prompt_id}
Fetches one full prompt on demand for explicit result inspection.

### GET /api/stats
Returns corpus statistics for the frontend stats bar.

---

## Qdrant Collection Schema

Collection name: `redlib`

Dense vectors:
- name: `dense`
- size: `1536`
- distance: `cosine`

Sparse vectors:
- name: `sparse`
- index: `SparseIndexParams()`

Payload schema:
```json
{
  "_node_content": "string",
  "_node_type": "TextNode",
  "source": "string",
  "technique": "string",
  "prompt_id": "string"
}
```

Payload indexes:
- `prompt_id`: `keyword`
- used by `GET /api/prompts/{prompt_id}` for direct full-prompt lookup
- `technique`: `keyword`
- used by query-time category filtering

Node content:
- prompt text lives in the `TextNode` body
- Qdrant payloads are written through LlamaIndex so `_node_content` and
  `_node_type` are preserved for `metadata_dict_to_node(...)`
- metadata stores only true metadata fields
- result excerpts and full-prompt lookup both read from node content

---

## LlamaIndex Component Map

| Module              | LlamaIndex Class       | Role                        |
|---------------------|------------------------|-----------------------------|
| `api/embedder.py`   | `OpenAIEmbedding`      | text-embedding-3-small      |
| `api/retriever.py`  | `QueryFusionRetriever` | Hybrid search + RRF         |
| `api/retriever.py`  | `QdrantVectorStore`    | Dense + sparse vector store |
| `api/retriever.py`  | `CohereRerank`         | Reranking postprocessor     |
| `api/router.py`     | `RetrieverQueryEngine` | Single corpus-grounded query engine |
| `api/synthesizer.py`| `ResponseSynthesizer`  | Answer generation           |
| `api/synthesizer.py`| `Anthropic`            | LLM for synthesis           |

---

## Environment Variables

| Variable            | Used By                                  | Purpose                      |
|---------------------|-------------------------------------------|------------------------------|
| `QDRANT_URL`        | `api/app.py`, `api/retriever.py`, `corpus/ingest.py` | Qdrant Cloud endpoint |
| `QDRANT_API_KEY`    | `api/app.py`, `api/retriever.py`, `corpus/ingest.py` | Qdrant authentication |
| `OPENAI_API_KEY`    | `api/embedder.py`, `corpus/ingest.py`     | Embeddings                   |
| `ANTHROPIC_API_KEY` | `api/synthesizer.py`, `corpus/discover_taxonomy.py`, `corpus/classify_corpus.py` | Claude Haiku usage |
| `COHERE_API_KEY`    | `api/retriever.py`                        | Cohere Rerank API            |
| `HUGGINGFACE_TOKEN` | `corpus/fetch_corpus.py`                  | Dataset snapshot access      |
| `DOPPLER_TOKEN`     | deployment/runtime                        | Secrets injection            |

---

## Local Development Setup

```bash
git clone https://github.com/nipun-ag/redlib
cd redlib

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

doppler login
doppler setup

doppler run -- uvicorn api.app:app --reload --port 8000
```

Frontend assets can be opened directly from `frontend/` or served with
any static file server during local development.

---

## Deployment

Deployment is split:
- frontend static assets from `frontend/`
- FastAPI backend deployed separately
- Doppler-managed secrets
- GitHub Actions deploy workflow on push to `main`

---

## Constraints

- Changing the embedding model invalidates stored vectors and requires
  re-ingestion.
- Raw corpus snapshots are immutable once captured.
- Downstream stages consume canonical JSONL rather than platform-native
  raw source files.
- Normalization must preserve semantic meaning while remaining deterministic.
- Taxonomy discovery and taxonomy application must stay separate stages.
- Ingestion consumes only finalized classified corpus artifacts.
- Prompt text is stored in the `TextNode` body, not in metadata.
- Ingestion enforces an 8000-token embedding limit per record using the exact embed-content string; oversized records are quarantined to `data/corpus/ingest_oversized.jsonl` rather than truncated or allowed to crash the run.
