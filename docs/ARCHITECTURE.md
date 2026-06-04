# RedLib — Architecture

## Overview
RedLib ingests ~3,500 real jailbreak prompts from public research
datasets, indexes them in Pinecone using a hybrid dense + sparse
approach, and exposes a FastAPI backend that runs a full production
RAG pipeline: semantic chunking → hybrid search → RRF → Cohere rerank
→ Claude Haiku synthesis. A Vanilla JS frontend serves two screens:
a gated landing page and the main search interface.

---

## File / Folder Structure

```
redlib/
├── app.py              # FastAPI app entry point. All API routes.
│                       # No business logic here — imports from modules.
├── rag.py              # Assembles the full LlamaIndex query pipeline.
│                       # Imports router, retriever, synthesizer.
├── ingest.py           # One-time ingestion script. Run manually.
│                       # Loads datasets → cleans → classifies →
│                       # chunks → embeds → upserts to Pinecone.
├── chunker.py          # Configures LlamaIndex SemanticSplitterNodeParser.
│                       # Sets similarity threshold, embed model.
├── embedder.py         # Configures OpenAI text-embedding-3-small.
│                       # Used by chunker and retriever.
├── retriever.py        # Configures LlamaIndex QueryFusionRetriever
│                       # (hybrid search + RRF) and CohereRerank
│                       # postprocessor.
├── router.py           # Configures LlamaIndex RouterQueryEngine.
│                       # Routes: semantic query vs conceptual question.
├── synthesizer.py      # Configures LlamaIndex ResponseSynthesizer
│                       # with Claude Haiku 4.5 as the LLM.
├── datasets.py         # HuggingFace dataset loaders. One function
│                       # per source dataset. Returns cleaned records.
├── classifier.py       # Calls Claude Haiku to assign one of 10
│                       # technique labels to each prompt during ingestion.
├── evaluate.py         # RAGAS evaluation suite. Run manually or on
│                       # sampled queries in background.
├── static/
│   ├── css/style.css   # Custom CSS layered on top of Tailwind CDN.
│   └── js/app.js       # All frontend logic. Fetch calls, DOM updates,
│                       # sidebar filter state, expand/collapse.
├── templates/
│   ├── landing.html    # Landing page. Disclaimer gate + consent flow.
│   └── index.html      # Main search interface. Sidebar + results.
├── data/
│   └── raw/            # Raw downloaded dataset files before ingestion.
│                       # Not committed to git (.gitignore).
├── docs/
│   ├── ARCHITECTURE.md # This file.
│   └── CONTEXT.md      # AI synthesis prompt rules and constraints.
├── .env.example        # Reference only. Lists required var names.
│                       # Never populate. Never commit real keys.
├── requirements.txt    # All Python dependencies.
├── CLAUDE.md           # Coding agent instructions.
├── DESIGN.md           # Full design system from Stitch source.
├── PROGRESS.md         # Session log and deferred features.
└── README.md           # Human-facing project description.
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
    "Persona Hijacking": 0,
    "Fictional Framing": 0
  },
  "result_count": 0,
  "query_type": "semantic | conceptual"
}
```

---

### GET /api/categories
Returns all technique categories with corpus counts.

Response:
```json
{
  "categories": [
    {
      "name": "string",
      "count": 0,
      "icon": "string"
    }
  ]
}
```

---

### GET /api/stats
Returns corpus statistics for the stats bar.

Response:
```json
{
  "total_prompts": 0,
  "total_sources": 0,
  "last_sync": "YYYY-MM-DD"
}
```

---

## Data Sources

| Dataset                                    | Source      | Est. Size | Quality         |
|--------------------------------------------|-------------|-----------|-----------------|
| verazuo/jailbreak_llms                     | HuggingFace | ~1,405    | High — CCS 2024 |
| TrustAIRLab/in-the-wild-jailbreak-prompts  | HuggingFace | ~900      | High            |
| rubend18/ChatGPT-Jailbreak-Prompts         | HuggingFace | ~160      | Medium          |
| jackhhao/jailbreak-classification          | HuggingFace | ~1,000    | High            |
| HarmBench                                  | GitHub      | ~400      | High — benchmark|

Estimated total after deduplication: 3,500 to 4,000 unique prompts.

---

## Technique Categories (10)

Assigned by classifier.py during ingestion via Claude Haiku:

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

## Pinecone Schema

Index type: hybrid (dense + sparse)

Each vector upserted with metadata:
```json
{
  "id": "source_dataset__prompt_id__chunk_index",
  "values": [/* dense vector, 1536 dims (text-embedding-3-small) */],
  "sparse_values": {/* BM25 sparse vector */},
  "metadata": {
    "text": "string",
    "technique": "string",
    "source": "string",
    "prompt_id": "string",
    "chunk_index": 0
  }
}
```

---

## Full Data Flow

### Ingestion (run once)
```
HuggingFace datasets
      ↓ datasets.py
Load + clean → LlamaIndex Document objects
      ↓ classifier.py
Claude Haiku assigns technique label → stored in metadata
      ↓ chunker.py
SemanticSplitterNodeParser → splits on cosine similarity drop
(threshold: 0.7, model: text-embedding-3-small)
Short prompts → single node, no split
      ↓ embedder.py
OpenAI text-embedding-3-small → dense vector per node
      ↓ retriever.py (BM25Encoder)
Pinecone BM25Encoder → sparse vector per node
      ↓ Pinecone
Upsert: dense vector + sparse vector + metadata
```

### Query Time
```
User query (POST /api/query)
      ↓ router.py (RouterQueryEngine)
      ├── semantic query → QueryFusionRetriever
      │         ↓
      │   Dense search (Pinecone vector similarity)
      │   Sparse search (Pinecone BM25)
      │         ↓ RRF (QueryFusionRetriever native)
      │   Merged ranked list
      │         ↓ CohereRerank postprocessor
      │   Top 5 reranked nodes
      │         ↓ synthesizer.py (ResponseSynthesizer + Haiku)
      │   Synthesized answer
      │
      └── conceptual question → Claude Haiku direct (no retrieval)
            ↓
      Direct answer

      ↓ app.py
Assemble response: answer + result cards + technique breakdown
      ↓
JSON response to frontend
```

---

## LlamaIndex Component Map

| Module          | LlamaIndex Class                  | Role                            |
|-----------------|-----------------------------------|---------------------------------|
| chunker.py      | SemanticSplitterNodeParser        | Semantic chunking at ingestion  |
| embedder.py     | OpenAIEmbedding                   | text-embedding-3-small          |
| retriever.py    | QueryFusionRetriever              | Hybrid search + RRF             |
| retriever.py    | PineconeVectorStore               | Dense + sparse vector store     |
| retriever.py    | CohereRerank                      | Reranking postprocessor         |
| router.py       | RouterQueryEngine                 | Query intent classification     |
| synthesizer.py  | ResponseSynthesizer               | Answer generation               |
| synthesizer.py  | Anthropic (Claude Haiku 4.5)      | LLM for synthesis               |

---

## Environment Variables

| Variable           | Used By              | Purpose                              |
|--------------------|----------------------|--------------------------------------|
| PINECONE_API_KEY   | retriever.py         | Pinecone authentication              |
| PINECONE_INDEX_NAME| retriever.py         | Target index name                    |
| OPENAI_API_KEY     | embedder.py          | text-embedding-3-small               |
| ANTHROPIC_API_KEY  | synthesizer.py       | Claude Haiku 4.5                     |
| COHERE_API_KEY     | retriever.py         | Cohere Rerank API                    |
| HUGGINGFACE_TOKEN  | datasets.py          | HuggingFace dataset access           |
| DOPPLER_TOKEN      | all                  | Secrets injection (production)       |

---

## Local Development Setup

```bash
# 1. Clone repo
git clone https://github.com/nipun-ag/redlib
cd redlib

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Doppler CLI (first time only)
# Mac: brew install dopplerhq/cli/doppler
# Linux: see https://docs.doppler.com/docs/install-cli
doppler login
doppler setup  # Select the redlib project and config

# 5. Run ingestion via Doppler (first time only)
doppler run -- python ingest.py

# 6. Start development server via Doppler
doppler run -- uvicorn app:app --reload --port 8000

# 7. Open browser
# http://localhost:8000
```

Note: Never create a real .env file with actual keys.
.env.example in the repo lists all required variable names
as a reference. All secrets live in Doppler only.

---

## Deployment (Hetzner VPS)

```
GitHub push to main
      ↓ GitHub Actions
SSH into Hetzner VPS
      ↓
git pull + pip install -r requirements.txt
      ↓
systemctl restart redlib
      ↓
systemd service runs: doppler run -- gunicorn app:app
Doppler injects all secrets into the process at start
      ↓
Nginx serves on port 80/443
Gunicorn runs FastAPI on port 8000 internally
Cloudflare proxies DNS + DDoS protection
Let's Encrypt handles SSL
```

Nginx config: reverse proxy from 443 → localhost:8000
Rate limiting: 10 requests/second per IP on /api/ routes

---

## Known Constraints and Gotchas

- Pinecone free tier: 1 index, 2GB storage. Sufficient for ~4,000
  vectors at 1536 dims but monitor usage as corpus grows.
- Semantic chunking requires an embedding pass at ingestion time,
  making ingest.py slower. This is expected — run it once.
- Changing the embedding model after ingestion invalidates all stored
  vectors. The entire index must be rebuilt.
- HarmBench requires GitHub download, not HuggingFace API. Handle
  separately in datasets.py.
- BM25Encoder must be fit on the full corpus before ingestion. Fit
  once, serialize, reuse. Do not refit on partial data.
- RAGAS evaluation requires OpenAI API calls internally. It is not
  free to run. Use sampled queries (20-30) not the full corpus.
- The "DETAILED REPORT" link on result cards has no backing page in
  Phase 1. Either remove it or wire to a modal.
