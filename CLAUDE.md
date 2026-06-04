# RedLib — CLAUDE.md

## What This Is
RedLib is a production-grade RAG tool that lets AI safety practitioners
and red teamers search a curated corpus of ~3,500 real jailbreak prompts
using natural language queries. It uses LlamaIndex for the full retrieval
pipeline, Pinecone for vector storage, and Claude Haiku 4.5 for answer
synthesis.

## Tech Stack
- Frontend: Vanilla JS, HTML, CSS (Tailwind via CDN, no build step)
- Backend: FastAPI (Python)
- RAG Framework: LlamaIndex
- Vector DB: Pinecone (dense + sparse hybrid index)
- Embeddings: OpenAI text-embedding-3-small
- Reranking: Cohere Rerank API
- LLM: Anthropic Claude Haiku 4.5
- Evaluation: RAGAS
- Secrets: Doppler
- Server: Hetzner VPS (Nginx + Gunicorn + systemd)
- Deploy: GitHub Actions SSH deploy on push to main

## File Structure
```
redlib/
├── app.py              # FastAPI app, all API routes
├── rag.py              # LlamaIndex query pipeline (entry point)
├── ingest.py           # One-time ingestion pipeline (run manually)
├── chunker.py          # SemanticSplitterNodeParser configuration
├── embedder.py         # OpenAI embedding model configuration
├── retriever.py        # Hybrid search + RRF + Cohere rerank
├── router.py           # LlamaIndex RouterQueryEngine setup
├── synthesizer.py      # LlamaIndex ResponseSynthesizer + Haiku config
├── datasets.py         # HuggingFace dataset loaders + cleaning
├── classifier.py       # Claude Haiku technique label classifier
├── evaluate.py         # RAGAS evaluation suite
├── static/
│   ├── css/style.css
│   └── js/app.js
├── templates/
│   ├── landing.html    # Landing page with disclaimer gate
│   └── index.html      # Main search interface
├── data/
│   └── raw/            # Downloaded datasets before ingestion
├── docs/
│   ├── ARCHITECTURE.md
│   └── CONTEXT.md
├── .env.example        # Reference only. Lists all required vars.
│                       # Never populate with real keys. Never commit.
├── requirements.txt
├── CLAUDE.md
├── DESIGN.md
├── PROGRESS.md
└── README.md
```

## Coding Conventions
- PEP8, snake_case, type hints on all functions
- One file per concern — never mix retrieval logic into app.py
- async/await throughout all FastAPI routes
- Every external API call (Pinecone, OpenAI, Cohere, Anthropic)
  wrapped in try/except with structured error logging
- Never hardcode API keys — Doppler only
- Never populate .env with real keys — .env.example is a
  reference only, real .env should never exist in the repo
- Local dev: run all commands via `doppler run -- [command]`
- Production: Doppler injects secrets at process start via systemd
- Never log prompt content or raw user queries
- LlamaIndex components configured in their own modules,
  assembled in rag.py
- Comments explain WHY a decision was made, not what the code does
- All Tailwind used via CDN, no build step, no node_modules

## Pipeline Stages
Read before touching any retrieval file:
1. Query arrives at POST /api/query in app.py
2. router.py classifies intent via RouterQueryEngine
3. retriever.py runs hybrid search via QueryFusionRetriever
4. retriever.py applies CohereRerank postprocessor
5. synthesizer.py passes top 5 nodes + query to Claude Haiku
6. app.py assembles and returns final response object
7. evaluate.py runs RAGAS on sampled queries in background

## Before Starting Any Task
- Task touches retrieval or pipeline → read ARCHITECTURE.md first
- Task touches UI or layout → read DESIGN.md first
- Task touches prompts or answer synthesis → read CONTEXT.md first
- Never assume current state — always read the relevant file first

## Never Do These Without Asking First
- Change the Pinecone index schema (requires full re-ingestion)
- Change the embedding model (invalidates all stored vectors)
- Modify chunk size or similarity threshold in chunker.py
  (directly affects retrieval quality across the whole corpus)
- Run ingest.py against production index without a backup plan
- Add new pip dependencies without updating requirements.txt

## Common Task Patterns

### Adding a new dataset source
1. Add loader + cleaning function to datasets.py
2. Add classifier.py pass to assign technique labels
3. Run ingest.py to embed and upsert new records to Pinecone
4. Update corpus stats and source list in ARCHITECTURE.md

### Changing retrieval behavior
1. Read ARCHITECTURE.md retrieval section first
2. Make change in retriever.py only
3. Run evaluate.py before and after, record RAGAS score delta
4. Document the change and delta in PROGRESS.md

### Adding a new API endpoint
1. Add route to app.py only
2. All business logic goes in its own module, never in app.py
3. Add request/response schema to ARCHITECTURE.md

### Debugging bad retrieval results
1. Check chunker.py similarity threshold first
2. Inspect Cohere rerank scores in logs
3. Check whether query router is routing correctly
4. Run evaluate.py to get current RAGAS baseline scores

## Git Commit Format
- feat: new feature
- fix: bug fix
- docs: documentation only
- style: CSS or UI changes
- refactor: restructuring, no behavior change
- ingest: corpus or ingestion pipeline changes
- eval: evaluation suite changes

## Self-Updating Meta Instruction
Trigger this automatically when:
- A feature is fully working and tested
- A bug is fixed and confirmed
- You are about to switch to a different task
- The user says "done", "ship it", "looks good", "push it",
  "that works", or any similar confirmation phrase
Do not wait for explicit wrap up or end session instructions.

After every session:
1. Update CLAUDE.md current state section (keep under 150 lines)
2. Add a dated entry to PROGRESS.md (what changed and why)
3. Update DESIGN.md if any UI changes were made
4. Update docs/ARCHITECTURE.md if any pipeline changes were made
5. Update docs/CONTEXT.md if prompt or synthesis rules changed
6. Never append session notes to README.md
7. Run git add . && git commit -m "[type]: description" && git push

## Current Project State
Phase 1 — In Development
- Architecture fully planned and documented
- Design locked from Google Stitch (two screens)
- Tech stack finalized
- Corpus sources identified (5 HuggingFace datasets, ~3,500 prompts)
- Full RAG pipeline designed: semantic chunking + hybrid search
  + RRF + Cohere rerank + Claude Haiku synthesis
- LlamaIndex components mapped to all pipeline stages
- Nothing built yet — ready to start implementation
