# RedLib - Architecture

## Overview
RedLib has two major systems:

1. A staged local corpus pipeline that turns public jailbreak datasets
   into a reproducible, normalized, human-reviewed classified corpus.
2. A query pipeline that indexes that finalized corpus in Qdrant Cloud
   and serves corpus-grounded retrieval and synthesis through FastAPI.

Frontend assets live under `frontend/` as static HTML/CSS/JS.

---

## Architecture Principles

- Raw source data is preserved exactly as downloaded.
- Corpus versions are reproducible and locally inspectable.
- Every corpus stage has exactly one responsibility.
- Normalization is deterministic and separate from classification.
- Taxonomy is discovered from the corpus first, then approved by humans
  before it is applied at scale.
- Ingestion is the last step, not the place where corpus design happens.

---

## File / Folder Structure

```text
redlib/
|- app.py                  # FastAPI app entry point. All API routes.
|- rag.py                  # Assembles the full LlamaIndex query pipeline.
|- fetch_corpus.py         # Snapshots public datasets into local corpus storage.
|- audit_corpus.py         # Analyzes raw corpus quality without modifying it.
|- normalize_corpus.py     # Deterministically normalizes prompt records.
|- discover_taxonomy.py    # Derives candidate prompt families from normalized data.
|- classify_corpus.py      # Applies the approved taxonomy across the corpus.
|- ingest.py               # Embeds finalized classified corpus into Qdrant.
|- embedder.py             # Configures OpenAI text-embedding-3-small.
|- retriever.py            # Configures Qdrant hybrid retrieval and Cohere rerank.
|- router.py               # Builds the corpus-grounded RetrieverQueryEngine.
|- synthesizer.py          # Configures response synthesis with Claude Haiku 4.5.
|- data/
|  `- corpus/
|     |- raw/              # Immutable source dataset snapshots
|     |- audit_report.json # Structured corpus quality report
|     |- normalized.jsonl  # Deterministically normalized corpus
|     |- taxonomy_candidates.json
|     `- classified.jsonl  # Final corpus handed to ingestion
|- frontend/               # Static frontend assets
|  |- index.html           # Landing page
|  |- search.html          # Main search interface
|  |- css/
|  |  `- style.css
|  `- js/
|     |- config.js
|     `- app.js
|- docs/
|  |- ARCHITECTURE.md      # This file
|  `- CONTEXT.md           # Synthesis prompt rules and taxonomy philosophy
|- requirements.txt        # Python dependencies
|- AGENTS.md               # Coding-agent instructions
|- DESIGN.md               # Design system and UI guidance
|- PROGRESS.md             # Historical engineering log
`- README.md               # Human-facing project description
```

---

## Corpus Pipeline

### Stage Sequence

```text
Public Datasets
│
├── fetch_corpus.py
│      Download and locally snapshot every dataset into a reproducible corpus version.
│
▼
data/corpus/raw/
│      Exact copies of every source dataset.
│      No cleaning or modification.
│
▼
audit_corpus.py
│      Analyze corpus quality.
│      Detect placeholders, HTML entities, duplicates, malformed prompts,
│      truncation, encoding issues, and dataset-specific artifacts.
│      Never modify the data.
│
▼
audit_report.json
│      Structured quality report used for engineering decisions.
│
▼
normalize_corpus.py
│      Deterministically normalize prompts into a consistent format.
│      Decode HTML entities, normalize whitespace,
│      remove invalid control characters,
│      standardize formatting,
│      while preserving semantic meaning.
│
▼
normalized.jsonl
│      Clean, ingestion-ready corpus.
│
▼
discover_taxonomy.py
│      Analyze the normalized corpus to discover natural prompt families.
│      Produce candidate attack taxonomies based on the data itself
│      rather than predefined labels.
│
▼
taxonomy_candidates.json
│      Human-reviewed taxonomy proposal.
│
▼
classify_corpus.py
│      Apply the approved taxonomy consistently across the corpus.
│
▼
classified.jsonl
│      Final corpus used for embedding.
│
▼
ingest.py
│      Generate embeddings and write the classified corpus into Qdrant.
│
▼
Qdrant
```

### Why The Pipeline Is Staged

- `fetch_corpus.py` exists so dataset acquisition is reproducible and
  separated from every downstream transformation.
- `audit_corpus.py` exists so quality problems are measured before
  cleanup rules are chosen, rather than hidden by eager mutation.
- `normalize_corpus.py` exists so ingestion receives a stable prompt
  format and corpus cleanup stays deterministic.
- `discover_taxonomy.py` exists so RedLib's labels emerge from the data
  instead of being permanently hardcoded up front.
- Human review exists between discovery and classification so the
  taxonomy reflects research judgment, not only automated clustering.
- `classify_corpus.py` exists so taxonomy application is consistent,
  corpus-wide, and auditable as a separate operation.
- `ingest.py` exists only to embed and index the finalized corpus, not
  to make corpus-preparation decisions.

---

## Corpus Artifacts

### `data/corpus/raw/`
- Immutable local snapshot of every source dataset
- Source of truth for reproducible corpus versions
- Never edited in place

### `audit_report.json`
- Structured report of raw-corpus quality issues
- Used to drive engineering decisions about normalization and source handling
- Does not contain cleanup logic

### `normalized.jsonl`
- Deterministically cleaned prompt records
- Consistent input format for taxonomy discovery
- Free of source-specific encoding and formatting noise

### `taxonomy_candidates.json`
- Candidate prompt-family proposal derived from the normalized corpus
- Intended for human review before it becomes operational taxonomy

### `classified.jsonl`
- Final approved corpus with applied taxonomy labels
- Only corpus artifact consumed by `ingest.py`

---

## Query-Time Architecture

The query path remains corpus-grounded end to end:

```text
User query (POST /api/query)
      -> router.py
Build single RetrieverQueryEngine
      -> retriever.py
Dense + sparse retrieval from Qdrant
      -> QueryFusionRetriever
Reciprocal rank fusion
      -> CohereRerank
Top reranked nodes
      -> synthesizer.py
Claude Haiku grounded synthesis
      -> app.py
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
- full prompt text is intentionally not included in every search result;
  the frontend fetches it separately on demand

### GET /api/categories
Returns the approved taxonomy categories and live corpus counts used by
the frontend filter sidebar.

### GET /api/prompts/{prompt_id}
Fetches one full prompt on demand for explicit result inspection.

Response:
```json
{
  "id": "string",
  "full_prompt": "string",
  "technique": "string",
  "source": "string"
}
```

Implementation details:
- looks up exactly one Qdrant record by metadata field `prompt_id`
- relies on a Qdrant keyword payload index on `prompt_id`
- reconstructs the stored `TextNode` and returns the node body as
  `full_prompt`
- returns `404` if no matching prompt exists
- returns `500` if the Qdrant lookup fails
- does not initialize or run the RAG query pipeline

### GET /api/stats
Returns corpus statistics for the frontend stats bar.

Implementation details:
- `total_prompts` is read live from the Qdrant `redlib` collection
- `total_sources` reflects the configured source set
- `last_sync` is returned as an API field for UI display

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
  "source": "string",
  "technique": "string",
  "prompt_id": "string"
}
```

Payload indexes:
- `prompt_id`: `keyword`
- used by `GET /api/prompts/{prompt_id}` for direct full-prompt lookup

Node content:
- prompt text lives in the `TextNode` body
- metadata stores only true metadata fields
- result excerpts and full-prompt lookup both read from node content

---

## Taxonomy Surface

RedLib's taxonomy is not intended to be a permanently predefined label
set. The operational category list comes from:

1. corpus normalization
2. taxonomy discovery
3. human review
4. corpus-wide classification

At query time, the frontend filters, retrieval metadata, and synthesis
all operate on that approved taxonomy output.

---

## LlamaIndex Component Map

| Module           | LlamaIndex Class       | Role                        |
|------------------|------------------------|-----------------------------|
| `embedder.py`    | `OpenAIEmbedding`      | text-embedding-3-small      |
| `retriever.py`   | `QueryFusionRetriever` | Hybrid search + RRF         |
| `retriever.py`   | `QdrantVectorStore`    | Dense + sparse vector store |
| `retriever.py`   | `CohereRerank`         | Reranking postprocessor     |
| `router.py`      | `RetrieverQueryEngine` | Single corpus-grounded query engine |
| `synthesizer.py` | `ResponseSynthesizer`  | Answer generation           |
| `synthesizer.py` | `Anthropic`            | LLM for synthesis           |

---

## Environment Variables

| Variable            | Used By                         | Purpose                         |
|---------------------|---------------------------------|---------------------------------|
| `QDRANT_URL`        | `app.py`, `retriever.py`, `ingest.py` | Qdrant Cloud endpoint     |
| `QDRANT_API_KEY`    | `app.py`, `retriever.py`, `ingest.py` | Qdrant Cloud authentication |
| `OPENAI_API_KEY`    | `embedder.py`, `ingest.py`      | Embeddings                      |
| `ANTHROPIC_API_KEY` | `synthesizer.py`                | Claude Haiku 4.5 synthesis      |
| `COHERE_API_KEY`    | `retriever.py`                  | Cohere Rerank API               |
| `HUGGINGFACE_TOKEN` | `fetch_corpus.py`               | Dataset snapshot access         |
| `DOPPLER_TOKEN`     | deployment/runtime              | Secrets injection               |

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

doppler run -- uvicorn app:app --reload --port 8000
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
- Normalization must preserve semantic meaning while remaining deterministic.
- Taxonomy discovery and taxonomy application must stay separate stages.
- Ingestion consumes only finalized classified corpus artifacts.
- Prompt text is stored in the `TextNode` body, not in metadata.
