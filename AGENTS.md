# RedLib - AGENTS.md

## What This Is
RedLib is a production-grade RAG tool for AI safety practitioners and
red teamers searching a curated corpus of real jailbreak prompts. It
uses a staged local corpus pipeline to produce a reproducible classified
dataset, then indexes that finalized corpus in Qdrant Cloud for
retrieval and synthesis.

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
|- app.py                # FastAPI app, all API routes
|- rag.py                # LlamaIndex query pipeline (entry point)
|- fetch_corpus.py       # Snapshot public datasets into local raw corpus storage
|- audit_corpus.py       # Analyze raw corpus quality without modifying source data
|- normalize_corpus.py   # Deterministically normalize prompts into a stable corpus format
|- discover_taxonomy.py  # Derive candidate attack families from normalized corpus data
|- classify_corpus.py    # Apply the approved taxonomy across the finalized corpus
|- ingest.py             # Embed the classified corpus into Qdrant
|- embedder.py           # OpenAI embedding model configuration
|- retriever.py          # Qdrant hybrid retrieval + RRF + Cohere rerank
|- router.py             # Corpus-grounded query engine assembly
|- synthesizer.py        # LlamaIndex ResponseSynthesizer + Haiku config
|- data/
|  `- corpus/
|     |- raw/            # Immutable source dataset snapshots
|     |- audit_report.json
|     |- normalized.jsonl
|     |- taxonomy_candidates.json
|     `- classified.jsonl
|- frontend/             # Static frontend assets
|  |- index.html         # Landing page with disclaimer gate
|  |- search.html        # Main search interface
|  |- css/
|  |  `- style.css
|  `- js/
|     |- config.js       # API base URL configuration
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
2. `router.py` builds a single `RetrieverQueryEngine`
3. `retriever.py` runs hybrid search via `QueryFusionRetriever`
4. `retriever.py` applies `CohereRerank`
5. `synthesizer.py` passes top nodes + query to Claude Haiku
6. `app.py` assembles and returns the response object

Current corpus pipeline:
1. `fetch_corpus.py` snapshots public datasets into `data/corpus/raw/`
2. `audit_corpus.py` detects quality issues without changing the raw corpus
3. `normalize_corpus.py` produces deterministic normalized prompt records
4. `discover_taxonomy.py` proposes natural prompt families from the corpus itself
5. Human review approves the taxonomy proposal
6. `classify_corpus.py` applies the approved taxonomy across the corpus
7. `ingest.py` embeds only the finalized `classified.jsonl` corpus into Qdrant

Each corpus-stage script has exactly one responsibility:
- `fetch_corpus.py`: acquisition and local snapshotting only
- `audit_corpus.py`: quality analysis only
- `normalize_corpus.py`: deterministic normalization only
- `discover_taxonomy.py`: taxonomy discovery only
- `classify_corpus.py`: taxonomy application only
- `ingest.py`: embedding and Qdrant writes only

## Corpus Principles
- Raw datasets remain untouched after snapshotting
- The corpus should be reproducible on each build
- Normalization must be deterministic
- Taxonomy should be discovered from the corpus before it is applied
- Human review sits between taxonomy discovery and corpus-wide classification
- Ingestion consumes only finalized classified corpus artifacts

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
- Modify raw corpus snapshots in `data/corpus/raw/`

## Common Task Patterns

### Adding a new dataset source
1. Extend `fetch_corpus.py` to snapshot the new source into raw corpus storage
2. Re-run corpus audit and normalization
3. Re-run taxonomy discovery and classification if the new source changes the corpus mix
4. Re-run `ingest.py` after the finalized classified corpus is ready
5. Update corpus notes in `ARCHITECTURE.md`

### Changing corpus preparation behavior
1. Read `ARCHITECTURE.md` corpus section first
2. Keep the change isolated to the responsible stage script
3. Preserve the one-responsibility rule for each stage
4. Document the change in `PROGRESS.md`

### Changing retrieval behavior
1. Read `ARCHITECTURE.md` retrieval section first
2. Make the change in the retrieval modules
3. Verify behavior against representative queries
4. Document the change in `PROGRESS.md`

### Adding a new API endpoint
1. Add route to `app.py`
2. Put business logic in its own module, never in `app.py`
3. Add request/response schema to `ARCHITECTURE.md`

### Debugging corpus quality issues
1. Inspect the affected raw snapshot in `data/corpus/raw/`
2. Check `audit_report.json` for corpus-wide patterns
3. Inspect `normalize_corpus.py` for deterministic cleanup rules
4. Confirm whether the issue belongs to normalization, taxonomy, or ingestion

### Debugging bad retrieval results
1. Inspect Cohere rerank scores in logs
2. Check whether query routing is correct
3. Inspect Qdrant filters, source nodes, and classified corpus assumptions

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
- All user queries are corpus-grounded through the same retrieval path;
  there is no direct conceptual LLM-only route
- Full prompt inspection is lazy-loaded through a dedicated backend
  endpoint; search results stay excerpt-based
- Corpus architecture is organized around a staged local workflow:
  fetch, audit, normalize, discover taxonomy, classify, ingest
- `fetch_corpus.py` is implemented as an acquisition-only raw snapshot
  stage with per-source metadata and clean rerun replacement behavior
- `audit_corpus.py` is implemented as a read-only raw corpus quality
  analysis stage that writes `data/corpus/audit_report.json`
- `normalize_corpus.py` is implemented as a deterministic provenance-
  preserving cleanup stage that writes `data/corpus/normalized.jsonl`
- Ingestion is defined as the final embedding step that consumes only
  classified corpus artifacts
- Prompt text lives in the `TextNode` body; metadata stores only
  `source`, `technique`, and `prompt_id`
- Frontend assets are implemented under `frontend/`
