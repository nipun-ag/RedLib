# RedLib - AGENTS.md

## What This Is
RedLib is a production-grade RAG tool for AI safety practitioners and
red teamers searching a curated corpus of real adversarial jailbreak
prompts. It uses a staged local corpus pipeline to produce a
reproducible classified dataset, then indexes that finalized corpus in
Qdrant Cloud for retrieval and synthesis.

## Tech Stack
- Frontend: React 19 + Vite + TypeScript + Tailwind CSS v4 + shadcn/ui
- Backend: FastAPI (Python)
- RAG Framework: LlamaIndex
- Vector DB: Qdrant Cloud (hybrid dense + sparse retrieval)
- Embeddings: OpenAI `text-embedding-3-small`
- Reranking: Cohere Rerank API
- LLM: Anthropic Claude Haiku 4.5
- Secrets: Doppler
- Server: Hetzner VPS (Nginx + Gunicorn + systemd)
- Deploy: GitHub Actions SSH deploy on push to `main` (API); Vercel for frontend

## Current Frontend/Backend Layout
Frontend and backend are deployed as separate services.

Frontend:
- React app lives in `frontend/` (Vite build → `frontend/dist/`)
- Routes:
  - `/` responsible-use gate
  - `/workspace` research workspace
  - `/search.html` legacy redirect to `/workspace`
- Local API calls use the Vite `/api` proxy; production defaults to
  `https://api-redlib.bynipun.com`

Backend:
- FastAPI app in `api/app.py`
- Query pipeline assembled in `api/rag.py`
- Retrieval backed by Qdrant Cloud

Local dev:
  Backend: `doppler run -- uvicorn api.app:app --reload --port 8000`
  Frontend: `cd frontend && npm install && npm run dev`
  (Vite serves on port 3000 and proxies `/api` to production by default)

## File Structure
```text
redlib/
|- api/
|  |- __init__.py
|  |- app.py              # FastAPI app, all API routes
|  |- rag.py              # LlamaIndex query pipeline assembly
|  |- embedder.py         # OpenAI embedding model configuration
|  |- retriever.py        # Qdrant hybrid retrieval + RRF + Cohere rerank
|  |- router.py           # Corpus-grounded query engine assembly
|  `- synthesizer.py      # LlamaIndex ResponseSynthesizer + Haiku config
|- corpus/
|  |- __init__.py
|  |- fetch_corpus.py     # Snapshot public datasets into local raw corpus storage
|  |- convert_sources.py  # Convert raw source formats into canonical JSONL records
|  |- audit_corpus.py     # Analyze canonical corpus quality without modifying source data
|  |- normalize_corpus.py # Deterministically normalize prompts from canonical source records
|  |- corpus_sampling.py  # Shared deterministic corpus sampling utilities
|  |- discover_taxonomy.py # Derive candidate attack families from normalized corpus data
|  |- classify_corpus.py  # Apply the approved taxonomy across the finalized corpus
|  `- ingest.py           # Embed the classified corpus into Qdrant
|- data/
|  `- corpus/
|     |- raw/             # Immutable source dataset snapshots
|     |- canonical/       # Canonical JSONL records with preserved provenance
|     |- audit_report.json
|     |- normalized.jsonl
|     |- proposed_taxonomy.json
|     |- classified.jsonl # Final classified corpus consumed by ingest
|     `- classified_with_subtechniques.jsonl # Archive copy with subtechniques preserved
|- docs/
|  |- ARCHITECTURE.md
|  |- CONTEXT.md
|  |- DESIGN.md
|  `- PROGRESS.md
|- frontend/               # React + Vite research UI
|  |- src/
|  |  |- pages/           # Gate and workspace routes
|  |  |- components/      # UI composition + shadcn primitives
|  |  `- lib/             # API client and taxonomy helpers
|  |- vercel.json         # SPA rewrites for Vercel
|  `- package.json
|- .impeccable/
|  `- design.json         # Machine-readable design-system extensions
|- requirements.txt
|- .env.example
|- .gitignore
|- PRODUCT.md
|- AGENTS.md
`- README.md
```

## Coding Conventions
- PEP8, snake_case, type hints on all functions
- One file per concern; never mix retrieval logic into `api/app.py`
- async/await throughout all FastAPI routes
- External API calls should use structured error logging
- Never hardcode API keys; Doppler only
- Never populate `.env` with real keys
- Local dev: run commands via `doppler run -- [command]`
- Production: Doppler injects secrets at process start
- LlamaIndex components configured in their own modules and assembled
  in `api/rag.py`
- Comments explain WHY a decision was made, not what the code does
- Frontend is React + Vite + TypeScript; keep API access in `src/lib/api.ts`
- Frontend taxonomy aliases are presentation-only: keep canonical backend
  category names as state and API values, and resolve user-facing labels
  through `categoryLabel()` in `src/lib/taxonomy.ts`
- Keep shared Python dependencies pinned in `requirements.txt` when a version
  is already verified across local and production environments;
  `fastembed==0.8.0` is the confirmed cross-platform baseline for
  Windows/Python 3.13 and Ubuntu/Python 3.12

## Pipeline Stages
Read before touching any retrieval file:
1. Query arrives at `POST /api/query` in `api/app.py`
2. `api/router.py` builds a single `RetrieverQueryEngine`
3. `api/retriever.py` runs hybrid search via `QueryFusionRetriever`
4. `api/retriever.py` applies `CohereRerank`
5. `api/synthesizer.py` passes top nodes + query to Claude Haiku
6. `api/app.py` assembles and returns the response object

Current corpus pipeline:
1. `python -m corpus.fetch_corpus` snapshots public datasets into `data/corpus/raw/`
2. `python -m corpus.convert_sources` converts supported raw source files into `data/corpus/canonical/`
3. `python -m corpus.audit_corpus` detects quality issues without changing the canonical corpus
4. `python -m corpus.normalize_corpus` produces deterministic normalized prompt records
5. `python -m corpus.discover_taxonomy` proposes natural prompt families from the corpus itself
6. Human review approves the taxonomy proposal
7. `python -m corpus.classify_corpus` applies the approved taxonomy across the corpus
8. `python -m corpus.ingest` embeds only the finalized `classified.jsonl` corpus into Qdrant
   while `classified_with_subtechniques.jsonl` remains an archive-only reference copy

Each corpus-stage script has exactly one responsibility:
- `corpus.fetch_corpus`: acquisition and local snapshotting only
- `corpus.convert_sources`: structural source conversion only
- `corpus.audit_corpus`: quality analysis only
- `corpus.normalize_corpus`: deterministic normalization only
- `corpus.discover_taxonomy`: taxonomy discovery only
- `corpus.classify_corpus`: taxonomy application only
- `corpus.ingest`: embedding and Qdrant writes only

## Corpus Principles
- Raw datasets remain untouched after snapshotting
- The corpus should be reproducible on each build
- The corpus is limited to adversarial prompts that manipulate,
  override, or bypass LLM safety behavior
- Pure harmful requests without a jailbreak mechanism are out of scope
- Normalization must be deterministic
- Taxonomy should be discovered from the corpus before it is applied
- Human review sits between taxonomy discovery and corpus-wide classification
- Ingestion consumes only finalized classified corpus artifacts

## Before Starting Any Task
- Task touches retrieval or pipeline -> read `docs/ARCHITECTURE.md` first
- Task touches UI or layout -> read `docs/DESIGN.md` first
- Task touches prompts or answer synthesis -> read `docs/CONTEXT.md` first
- Never assume current state -> always read the relevant file first

## Never Do These Without Asking First
- Change the Qdrant collection schema (requires full re-ingestion)
- Change the embedding model (invalidates stored vectors)
- Run `python -m corpus.ingest` against production without a backup plan
- Add new pip dependencies without updating `requirements.txt`
- Modify raw corpus snapshots in `data/corpus/raw/`

## Common Task Patterns

### Adding a new dataset source
1. Extend `corpus/fetch_corpus.py` to snapshot the new source into raw corpus storage
2. Re-run `python -m corpus.convert_sources` to refresh the canonical corpus
3. Re-run `python -m corpus.audit_corpus` and `python -m corpus.normalize_corpus`
4. Re-run `python -m corpus.discover_taxonomy` and `python -m corpus.classify_corpus` if the new source changes the corpus mix
5. Re-run `python -m corpus.ingest` after the finalized classified corpus is ready
6. Update corpus notes in `docs/ARCHITECTURE.md`

### Changing corpus preparation behavior
1. Read `docs/ARCHITECTURE.md` corpus section first
2. Keep the change isolated to the responsible stage script
3. Preserve the one-responsibility rule for each stage
4. Document the change in `docs/PROGRESS.md`

### Changing retrieval behavior
1. Read `docs/ARCHITECTURE.md` retrieval section first
2. Make the change in the retrieval modules under `api/`
3. Verify behavior against representative queries
4. Document the change in `docs/PROGRESS.md`

### Adding a new API endpoint
1. Add route to `api/app.py`
2. Put business logic in its own module, never in `api/app.py`
3. Add request/response schema to `docs/ARCHITECTURE.md`

### Debugging corpus quality issues
1. Inspect the affected raw snapshot in `data/corpus/raw/`
2. Inspect the converted canonical file in `data/corpus/canonical/`
3. Check `data/corpus/audit_report.json` for corpus-wide patterns
4. Inspect `corpus/normalize_corpus.py` for deterministic cleanup rules
5. Confirm whether the issue belongs to conversion, normalization, taxonomy, or ingestion

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
2. Add a dated entry to `docs/PROGRESS.md` (what changed and why)
3. Update `docs/DESIGN.md` if any UI changes were made
4. Update `docs/ARCHITECTURE.md` if any pipeline changes were made
5. Update `docs/CONTEXT.md` if prompt or synthesis rules changed
6. Never append session notes to `README.md`
7. Run `git add . && git commit -m "[type]: description" && git push`

## Current Project State
Phase 1 - In Development / Production
- For full technical detail on the retrieval pipeline, API surface, Qdrant
  schema, and corpus stages, see `docs/ARCHITECTURE.md`.
- Backend query pipeline is implemented under `api/` and deployed on
  Hetzner behind Nginx at `api-redlib.bynipun.com`
- Frontend v2 (branch `v2`) is a React + Vite + shadcn rebuild under
  `frontend/` with the Ink & Platinum design system; design baseline
  lives in the normative `docs/DESIGN.md`, machine-readable extensions
  live in `.impeccable/design.json`, and product context lives in `PRODUCT.md`
- Technique names use frontend-only display aliases defined in
  `frontend/src/lib/taxonomy.ts`; canonical taxonomy names remain unchanged
  in frontend state, API requests/responses, Qdrant, and corpus artifacts
- Local frontend: `cd frontend && npm run dev` (port 3000, `/api` proxy)
- Vercel should use Root Directory `frontend`, Build `npm run build`,
  Output `dist`
- Corpus stages, in order: fetch snapshots sources; convert builds
  canonical records; audit measures quality; normalize cleans prompts;
  discover proposes taxonomy; classify applies approved labels; ingest
  embeds the finalized corpus.
- `requirements.txt` pins all production dependencies to exact versions
  verified on Windows/Python 3.13 and Ubuntu/Python 3.12, including
  `fastembed==0.8.0` and `slowapi==0.1.10`
- API deploys run automatically on push to `main`, installing
  dependencies, restarting systemd, and health-checking the API
- Backend/API contracts were not changed by the v2 frontend rebuild
