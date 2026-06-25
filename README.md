# RedLib

RedLib is a retrieval-augmented search tool for AI safety researchers
and red teamers working with real jailbreak prompts. It ingests a
curated corpus from public research datasets, stores hybrid vectors in
Qdrant Cloud, and exposes a FastAPI backend for natural-language search
and synthesis.

---

## Why It Exists

Useful jailbreak examples are spread across multiple datasets and are
hard to compare in one place. RedLib brings those sources together so
contributors can inspect attack patterns, filter by technique, and query
the corpus with plain language instead of manually searching raw files.

---

## How It Works

At a high level, RedLib has two parts:

- A one-time ingestion pipeline that loads public datasets, deduplicates
  prompt text, classifies each prompt into one of ten technique labels,
  embeds the prompts, and stores them in Qdrant.
- A query pipeline that runs hybrid retrieval, reranks the results, and
  produces a short synthesized answer grounded in the retrieved prompts.

The frontend lives in `frontend/` as static HTML, CSS, and JavaScript.
The backend API lives in `app.py`. Detailed implementation notes belong
in [docs/ARCHITECTURE.md](/C:/Users/nipun/projects/RedLib/docs/ARCHITECTURE.md).

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
| Data Sources  | Hugging Face datasets              |

---

## Data Sources

The current ingestion pipeline loads prompts from:

- `TrustAIRLab/in-the-wild-jailbreak-prompts`
- `rubend18/ChatGPT-Jailbreak-Prompts`
- `jackhhao/jailbreak-classification`
- `swiss-ai/harmbench` (`HumanJailbreaks`)

---

## Setup

```bash
git clone https://github.com/nipun-ag/redlib
cd redlib

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt fastapi uvicorn pydantic
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

The project is intended to be run with Doppler-managed secrets:

```bash
doppler login
doppler setup
```

---

## Ingest The Corpus

Run ingestion after your environment variables are available:

```bash
doppler run -- python ingest.py
```

The current ingestion flow:

- loads and deduplicates dataset records
- classifies each prompt into a technique category
- resumes from `ingest_checkpoint.json` if a prior run was interrupted
- embeds prompt content and inserts it into the `redlib` Qdrant collection
- skips prompts that exceed the embedding token budget

You only need to re-run ingestion when the corpus or vector schema changes.

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

- `ingest.py`: dataset loading, classification, embedding, and Qdrant insertion
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
