# RedLib

A production-grade RAG tool for AI safety practitioners and red teamers
to search a curated corpus of real adversarial prompts. Query 3,500+
jailbreak examples by technique, attack pattern, or specific prompt
using natural language — powered by a hybrid search pipeline with
semantic chunking, reciprocal rank fusion, and reranking.

---

## Why It Exists

Real jailbreak prompts are scattered across academic datasets, GitHub
repositories, and research papers with no unified search interface.
RedLib indexes the best public collections into a single queryable
corpus — so red teamers can find attack patterns in seconds instead
of hours.

---

## What It Does

- Natural language search across ~3,500 real jailbreak prompts
- Hybrid search: dense vector similarity + BM25 keyword matching
- Reciprocal rank fusion merges both result lists
- Cohere reranking for second-pass result scoring
- AI-synthesized summary (Claude Haiku) for every query
- 10 technique categories with sidebar filtering
- Responsible use gate on landing page
- RAGAS evaluation suite for pipeline quality measurement

---

## Tech Stack

| Layer          | Technology                        |
|----------------|-----------------------------------|
| Frontend       | Vanilla JS, HTML, CSS (Tailwind)  |
| Backend        | FastAPI (Python)                  |
| RAG Framework  | LlamaIndex                        |
| Vector DB      | Pinecone (hybrid index)           |
| Embeddings     | OpenAI text-embedding-3-small     |
| Reranking      | Cohere Rerank API                 |
| LLM            | Anthropic Claude Haiku 4.5        |
| Evaluation     | RAGAS                             |
| Hosting        | Hetzner VPS (Nginx + Gunicorn)    |
| Deploy         | GitHub Actions                    |

---

## Data Sources

| Dataset                                   | Size    |
|-------------------------------------------|---------|
| verazuo/jailbreak_llms (CCS 2024)         | ~1,405  |
| TrustAIRLab/in-the-wild-jailbreak-prompts | ~900    |
| rubend18/ChatGPT-Jailbreak-Prompts        | ~160    |
| jackhhao/jailbreak-classification         | ~1,000  |
| HarmBench                                 | ~400    |

---

## Running Locally

```bash
git clone https://github.com/nipun-ag/redlib
cd redlib
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Doppler CLI and connect to project
doppler login
doppler setup

doppler run -- python ingest.py   # First time only
doppler run -- uvicorn app:app --reload --port 8000
```

Open http://localhost:8000

All secrets are managed via Doppler. See .env.example for the
full list of required variable names.

---

## Environment Variables

All secrets are managed via Doppler. Never create a real .env file.
The .env.example in the repo lists required variable names only.

```
PINECONE_API_KEY
PINECONE_INDEX_NAME
OPENAI_API_KEY
ANTHROPIC_API_KEY
COHERE_API_KEY
HUGGINGFACE_TOKEN
```

---

## Deployment

Hosted on Hetzner VPS with Nginx, Gunicorn, and systemd.
Auto-deploys on push to main via GitHub Actions SSH deploy.
Cloudflare handles DNS and DDoS protection.
Secrets managed via Doppler.

---

## Responsible Use

This tool contains real adversarial prompts collected from public
research datasets. It is intended solely for AI safety research,
red teaming, and educational purposes. Users must acknowledge
responsible use before accessing the corpus.

---

## Status

In Development — Phase 1
