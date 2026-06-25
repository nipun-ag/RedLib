# RedLib - AGENTS.md

## What This Is
RedLib is a production-grade RAG tool that lets AI safety practitioners
and red teamers search a curated corpus of real jailbreak prompts using
natural language queries. It uses LlamaIndex for the retrieval pipeline,
Qdrant Cloud for vector storage, and Claude Haiku 4.5 for answer
synthesis.

## Tech Stack
- Frontend: Vanilla JS, HTML, CSS (Tailwind via CDN, no build step)
- Backend: FastAPI (Python)
- RAG Framework: LlamaIndex
- Vector DB: Qdrant Cloud (hybrid dense + sparse retrieval)
- Embeddings: OpenAI `text-embedding-3-small`
- Reranking: Cohere Rerank API
- LLM: Anthropic Claude Haiku 4.5
- Secrets: Doppler
- Server: Hetzner VPS (Nginx + Gunicorn + systemd)
- Deploy: GitHub Actions SSH deploy on push to `main`

## Current Frontend/Backend Layout
Frontend and backend are deployed as separate services.

Frontend:
- Static assets live in `frontend/`

Backend:
- FastAPI app in `app.py`
- Query pipeline assembled in `rag.py`
- Retrieval backed by Qdrant Cloud

Local dev:
  Backend: `doppler run -- uvicorn app:app --reload --port 8000`
  Frontend: open `frontend/index.html` directly in browser, or use
            any static file server from the `frontend/` directory

## File Structure
```text
redlib/
|- app.py              # FastAPI app, all API routes
|- rag.py              # LlamaIndex query pipeline (entry point)
|- ingest.py           # Ingestion pipeline (run manually)
|- embedder.py         # OpenAI embedding model configuration
|- retriever.py        # Qdrant hybrid retrieval + RRF + Cohere rerank
|- router.py           # LlamaIndex RouterQueryEngine setup
|- synthesizer.py      # LlamaIndex ResponseSynthesizer + Haiku config
|- data_loader.py      # HuggingFace dataset loaders + cleaning
|- classifier.py       # Claude Haiku technique label classifier
|- frontend/           # Static frontend assets
|  |- index.html       # Landing page with disclaimer gate
|  |- search.html      # Main search interface
|  |- css/
|  |  `- style.css
|  `- js/
|     |- config.js     # API base URL configuration
|     `- app.js
|- docs/
|  |- ARCHITECTURE.md
|  `- CONTEXT.md
|- requirements.txt
|- AGENTS.md
|- DESIGN.md
|- PROGRESS.md
`- README.md
```

## Coding Conventions
- PEP8, snake_case, type hints on all functions
- One file per concern - never mix retrieval logic into `app.py`
- async/await throughout all FastAPI routes
- External API calls should use structured error logging
- Never hardcode API keys - Doppler only
- Never populate `.env` with real keys
- Local dev: run commands via `doppler run -- [command]`
- Production: Doppler injects secrets at process start
- LlamaIndex components configured in their own modules,
  assembled in `rag.py`
- Comments explain WHY a decision was made, not what the code does
- All Tailwind used via CDN, no build step, no `node_modules`

## Pipeline Stages
Read before touching any retrieval file:
1. Query arrives at `POST /api/query` in `app.py`
2. `router.py` classifies intent via `RouterQueryEngine`
3. `retriever.py` runs hybrid search via `QueryFusionRetriever`
4. `retriever.py` applies `CohereRerank`
5. `synthesizer.py` passes top nodes + query to Claude Haiku
6. `app.py` assembles and returns the response object

Current ingestion pipeline:
1. `data_loader.py` loads and deduplicates dataset records
2. `ingest.py` resumes from `ingest_checkpoint.json` when present
3. `classifier.py` labels prompts via `classify_with_timeout()`
4. `ingest.py` saves checkpoint progress during classification
5. `embedder.py` configures `text-embedding-3-small`
6. `ingest.py` ensures the Qdrant collection exists
7. `ingest.py` stores prompt text in the `TextNode` body
8. `ingest.py` stores only `source`, `technique`, and `prompt_id` in metadata
9. `ingest.py` logs token counts for raw prompt text and embedded node content
10. `ingest.py` skips genuinely oversized prompts with a token-based guard
11. `ingest.py` inserts nodes into Qdrant in batches
12. `ingest.py` removes the checkpoint after a successful full run

## Before Starting Any Task
- Task touches retrieval or pipeline -> read `ARCHITECTURE.md` first
- Task touches UI or layout -> read `DESIGN.md` first
- Task touches prompts or answer synthesis -> read `CONTEXT.md` first
- Never assume current state -> always read the relevant file first

## Never Do These Without Asking First
- Change the Qdrant collection schema (requires full re-ingestion)
- Change the embedding model (invalidates stored vectors)
- Run `ingest.py` against production without a backup plan
- Add new pip dependencies without updating `requirements.txt`

## Common Task Patterns

### Adding a new dataset source
1. Add loader + cleaning function to `data_loader.py`
2. Add `classifier.py` pass to assign technique labels
3. Run `ingest.py` to embed and upsert new records to Qdrant
4. Update corpus stats and source list in `ARCHITECTURE.md`

### Changing retrieval behavior
1. Read `ARCHITECTURE.md` retrieval section first
2. Make the change in the retrieval modules
3. Verify behavior against representative queries
4. Document the change in `PROGRESS.md`

### Adding a new API endpoint
1. Add route to `app.py`
2. Put business logic in its own module, never in `app.py`
3. Add request/response schema to `ARCHITECTURE.md`

### Debugging bad ingestion results
1. Inspect checkpoint resume behavior in `ingest.py`
2. Inspect token-count logs and oversized-prompt warnings
3. Check Qdrant collection setup and batch-insert logs

### Debugging bad retrieval results
1. Inspect Cohere rerank scores in logs
2. Check whether query routing is correct
3. Inspect Qdrant filters, source nodes, and ingestion logs

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
1. Update AGENTS.md current state section (keep under 150 lines)
2. Add a dated entry to PROGRESS.md (what changed and why)
3. Update DESIGN.md if any UI changes were made
4. Update docs/ARCHITECTURE.md if any pipeline changes were made
5. Update docs/CONTEXT.md if prompt or synthesis rules changed
6. Never append session notes to README.md
7. Run git add . && git commit -m "[type]: description" && git push

## Current Project State
Phase 1 - In Development
- Backend query pipeline is implemented
- Ingestion is implemented with checkpoint resume support, timeout-wrapped
  classification, token counting, and oversized-prompt skipping safeguards
- Prompt text lives in the `TextNode` body; metadata stores only
  `source`, `technique`, and `prompt_id`
- Frontend assets are implemented under `frontend/`
