# RedLib - Architecture

## Overview
RedLib ingests a corpus of real jailbreak prompts from public research
datasets, indexes them in Qdrant Cloud using hybrid dense + sparse
retrieval, and exposes a FastAPI backend that runs a RAG pipeline:
hybrid search -> RRF -> Cohere rerank -> Claude Haiku synthesis.

Frontend assets live under `frontend/` as static HTML/CSS/JS.

---

## File / Folder Structure

```text
redlib/
|- app.py              # FastAPI app entry point. All API routes.
|- rag.py              # Assembles the full LlamaIndex query pipeline.
|- ingest.py           # Ingestion script. Run manually.
|- embedder.py         # Configures OpenAI text-embedding-3-small.
|- retriever.py        # Configures Qdrant hybrid retrieval and Cohere rerank.
|- router.py           # Configures LlamaIndex RouterQueryEngine.
|- synthesizer.py      # Configures response synthesis with Claude Haiku 4.5.
|- data_loader.py      # HuggingFace dataset loaders and record cleaning.
|- classifier.py       # Assigns one of 10 technique labels during ingestion.
|- frontend/           # Static frontend assets
|  |- index.html       # Landing page
|  |- search.html      # Main search interface
|  |- css/
|  |  `- style.css
|  `- js/
|     |- config.js
|     `- app.js
|- docs/
|  |- ARCHITECTURE.md  # This file
|  `- CONTEXT.md       # Synthesis prompt rules and constraints
|- requirements.txt    # Python dependencies
|- AGENTS.md           # Coding-agent instructions
|- DESIGN.md           # Design system and UI guidance
|- PROGRESS.md         # Session log and project progress
`- README.md           # Human-facing project description
```

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
    "Persona Hijacking": 0
  },
  "result_count": 0,
  "query_type": "semantic | conceptual"
}
```

Implementation details:
- `category_filter` is applied as a metadata filter on `technique`
- `prompt_excerpt` is built from the node body, not from metadata
- `query_type` is `"semantic"` when source nodes are returned, otherwise `"conceptual"`

### GET /api/categories
Returns the technique-category list used by the frontend.

### GET /api/stats
Returns corpus statistics for the frontend stats bar.

---

## Data Sources

Current ingestion code loads:

| Loader Function     | Dataset / Configs                                        |
|---------------------|----------------------------------------------------------|
| `load_trustairlab`  | `TrustAIRLab/in-the-wild-jailbreak-prompts` (2 configs) |
| `load_rubend18`     | `rubend18/ChatGPT-Jailbreak-Prompts`                     |
| `load_jackhhao`     | `jackhhao/jailbreak-classification`                      |
| `load_harmbench`    | `swiss-ai/harmbench` (`HumanJailbreaks`)                 |

`load_all_datasets()` deduplicates records on the raw `text` field.

---

## Technique Categories

Assigned by `classifier.py` during ingestion:

1. Persona Hijacking
2. Fictional Framing
3. Authority Impersonation
4. Token Manipulation
5. Gradual Escalation
6. Hypothetical Distancing
7. Instruction Injection
8. Social Engineering
9. Multi-language Switching
10. Payload Splitting

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

`ingest.py` creates the collection if it does not exist. `retriever.py`
and `ingest.py` both connect to the same collection.

---

## Node and Metadata Schema

Each prompt is stored as a `TextNode`.

Prompt text:
- lives in the `TextNode` body (`TextNode.text`)
- is the source used for retrieval excerpts
- remains available for retrieval and synthesis without storing it in metadata

Metadata stored on each node:
```json
{
  "source": "string",
  "technique": "string",
  "prompt_id": "string"
}
```

`metadata["text"]` is intentionally not stored. This prevents LlamaIndex
from duplicating the full prompt in the embedding input when it builds
the content used for embedding.

ID format:
- `generate_id(source, text)` -> `"{source}__{md5_prefix}"`
- `prompt_id` stored in metadata is the hash suffix after `__`

---

## Full Data Flow

### Ingestion
```text
HuggingFace datasets
      -> data_loader.py
Load + clean + deduplicate records
      -> ingest.py checkpoint loader
Resume prior classification progress if ingest_checkpoint.json exists
      -> classifier.py
Assign technique label with timeout protection
      -> ingest.py checkpoint saver
Persist classified progress during long runs
      -> embedder.py
Configure OpenAI text-embedding-3-small
      -> ingest.py
Create TextNode objects with prompt text in the node body
      -> LlamaIndex embed path
Embed node content
      -> Qdrant
Insert dense + sparse vectors with metadata into collection redlib
```

### Query Time
```text
User query (POST /api/query)
      -> router.py (RouterQueryEngine)
      |-- semantic query -> QueryFusionRetriever
      |         ->
      |   Dense search + sparse search in Qdrant
      |         -> RRF
      |   Merged ranked list
      |         -> CohereRerank
      |   Top reranked nodes
      |         -> synthesizer.py
      |   Claude Haiku synthesized answer
      |
      `-- conceptual question -> direct answer path

      -> app.py
Assemble response: answer + result cards + technique breakdown
      ->
JSON response to frontend
```

---

## Ingestion Safeguards

Current `ingest.py` includes:

- Checkpoint resume via `ingest_checkpoint.json`
- Classification timeout protection via `classify_with_timeout()`
- Token counting using `tiktoken` for the embedding model
- Logging of both raw prompt token count and exact embedded-content token count
- Oversized prompt skip guard based on the exact content that will be embedded
- Batch insertion logging around `index.insert_nodes(nodes)`

Checkpoint behavior:
- stores classified records plus the last processed index
- allows long ingestion runs to resume after interruption
- removes the checkpoint file after a successful full run

---

## LlamaIndex Component Map

| Module           | LlamaIndex Class       | Role                        |
|------------------|------------------------|-----------------------------|
| `embedder.py`    | `OpenAIEmbedding`      | text-embedding-3-small      |
| `retriever.py`   | `QueryFusionRetriever` | Hybrid search + RRF         |
| `retriever.py`   | `QdrantVectorStore`    | Dense + sparse vector store |
| `retriever.py`   | `CohereRerank`         | Reranking postprocessor     |
| `router.py`      | `RouterQueryEngine`    | Query intent classification |
| `synthesizer.py` | `ResponseSynthesizer`  | Answer generation           |
| `synthesizer.py` | `Anthropic`            | LLM for synthesis           |

---

## Environment Variables

Actual variables used by the current code:

| Variable            | Used By                         | Purpose                    |
|---------------------|---------------------------------|----------------------------|
| `QDRANT_URL`        | `retriever.py`, `ingest.py`     | Qdrant Cloud endpoint      |
| `QDRANT_API_KEY`    | `retriever.py`, `ingest.py`     | Qdrant Cloud authentication|
| `OPENAI_API_KEY`    | `embedder.py`                   | Embeddings                 |
| `ANTHROPIC_API_KEY` | `classifier.py`, `synthesizer.py` | Claude Haiku 4.5        |
| `COHERE_API_KEY`    | `retriever.py`                  | Cohere Rerank API          |
| `HUGGINGFACE_TOKEN` | `data_loader.py`                | HuggingFace dataset access |
| `DOPPLER_TOKEN`     | deployment/runtime              | Secrets injection          |

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

doppler run -- python ingest.py
doppler run -- uvicorn app:app --reload --port 8000
```

Frontend assets can be opened directly from `frontend/` or served with any
static file server during local development.

---

## Deployment

Deployment is split:
- frontend static assets from `frontend/`
- FastAPI backend deployed separately
- Doppler-managed secrets
- GitHub Actions deploy workflow on push to `main`

---

## Constraints

- Changing the embedding model invalidates stored vectors and requires re-ingestion.
- Prompt text is stored in the `TextNode` body, not in metadata.
- Oversize protection is based on the exact content sent to the embedding model.
