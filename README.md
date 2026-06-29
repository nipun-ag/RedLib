# RedLib

RedLib is a retrieval-augmented research tool for AI safety
practitioners and red teamers working with real jailbreak prompts. It
combines a local corpus pipeline with Qdrant-backed retrieval
so contributors can search, inspect, and synthesize patterns across a
curated prompt corpus.

---

## Why It Exists

Useful jailbreak prompts are scattered across public datasets and often
arrive with inconsistent formatting, duplicate records, and weak
taxonomy. RedLib exists to turn that messy source material into a
reproducible research corpus that can be audited, classified, embedded,
and queried reliably.

---

## How It Works

RedLib has two high-level systems:

- A staged corpus pipeline that snapshots public datasets locally,
  audits quality, normalizes prompts deterministically, discovers a
  taxonomy from the corpus itself, applies a human-approved taxonomy
  consistently, and only then hands the finalized corpus to ingestion.
- A query pipeline that retrieves relevant prompts from Qdrant, reranks
  them, and produces a short grounded synthesis for the user.

The frontend lives in `frontend/` as static HTML, CSS, and JavaScript.
The backend API lives in `app.py`. Detailed implementation notes belong
in [docs/ARCHITECTURE.md](/C:/Users/nipun/projects/RedLib/docs/ARCHITECTURE.md).

---

## Corpus Workflow

At a high level, the corpus pipeline is:

1. `fetch_corpus.py` snapshots public datasets into local raw corpus
   storage under `data/corpus/raw/`.
2. `convert_sources.py` converts supported raw source files into a
   canonical JSONL corpus under `data/corpus/canonical/` without
   changing their meaning or deciding which field is the prompt.
3. `audit_corpus.py` evaluates canonical corpus quality without
   modifying the preserved source data.
4. `normalize_corpus.py` produces a deterministic, ingestion-ready
   normalized corpus from the canonical JSONL records.
5. `discover_taxonomy.py` derives candidate prompt families from the
   normalized data.
6. Human review approves the taxonomy proposal.
7. `classify_corpus.py` applies the approved taxonomy across the full
   corpus.
8. `ingest.py` embeds only the finalized classified corpus and writes it
   to Qdrant.

This design keeps raw source data untouched, makes the corpus
reproducible on each build, and separates data cleaning, taxonomy design, and vector
ingestion into distinct responsibilities.

---

## Current Stack

| Layer         | Technology                         |
|---------------|------------------------------------|
| Frontend      | Vanilla JS, HTML, CSS (Tailwind)   |
| Backend       | FastAPI                            |
| RAG Framework | LlamaIndex                         |
| Vector Store  | Qdrant Cloud                       |
| Embeddings    | OpenAI `text-embedding-3-small`    |
| Reranking     | Cohere Rerank API                  |
| Synthesis     | Anthropic Claude Haiku 4.5         |
| Corpus Input  | Public datasets, locally snapshotted |

---

## Setup

```bash
git clone https://github.com/nipun-ag/redlib
cd redlib

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

RedLib expects the environment variables listed in
[.env.example](/C:/Users/nipun/projects/RedLib/.env.example):

```text
QDRANT_URL
QDRANT_API_KEY
OPENAI_API_KEY
ANTHROPIC_API_KEY
COHERE_API_KEY
HUGGINGFACE_TOKEN
```

The project is intended to run with Doppler-managed secrets:

```bash
doppler login
doppler setup
```

---

## Run The App

Start the backend API:

```bash
doppler run -- uvicorn app:app --reload --port 8000
```

Serve the frontend from the `frontend/` directory in a second terminal:

```bash
python -m http.server 3000 --directory frontend
```

Then open:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`

The checked-in frontend configuration points at `http://localhost:8000`
for API requests.

---

## Repository Guide

- `fetch_corpus.py`: snapshot public datasets into local raw corpus storage
- `convert_sources.py`: convert raw JSONL and CSV source files into canonical JSONL records with provenance
- `audit_corpus.py`: analyze canonical corpus quality without modifying source data
- `normalize_corpus.py`: deterministically normalize prompts from canonical source records into a stable corpus format
- `discover_taxonomy.py`: derive candidate attack families from the normalized corpus
- `classify_corpus.py`: apply the approved taxonomy across the corpus
- `ingest.py`: embed the finalized classified corpus into Qdrant
- `app.py`: FastAPI routes
- `rag.py`: query-pipeline assembly
- `retriever.py`: hybrid retrieval and reranking
- `synthesizer.py`: answer synthesis
- `frontend/`: static UI

For contributor workflow and repo-specific guardrails, see
[AGENTS.md](/C:/Users/nipun/projects/RedLib/AGENTS.md).

---

## Responsible Use

RedLib contains real adversarial prompts collected from public research
datasets. It is intended for AI safety research, red teaming, and
educational use. The frontend includes a responsible-use gate before
showing the searchable corpus.
