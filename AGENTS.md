# RedLib - AGENTS.md

## What This Is
RedLib is a production-grade RAG tool for AI safety practitioners and
red teamers searching a curated corpus of real adversarial jailbreak
prompts. It uses a staged local corpus pipeline to produce a
reproducible classified dataset, then indexes that finalized corpus in
Qdrant Cloud for retrieval and synthesis.

## Tech Stack
- Frontend: Vanilla HTML + CSS + JavaScript
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
- Static frontend assets live in `frontend/`
- Pages:
  - `index.html` responsible-use gate
  - `search.html` main research workspace
- Shared assets:
  - `css/style.css`
  - `js/config.js`
  - `js/app.js`

Backend:
- FastAPI app in `api/app.py`
- Query pipeline assembled in `api/rag.py`
- Retrieval backed by Qdrant Cloud

Local dev:
  Backend: `doppler run -- uvicorn api.app:app --reload --port 8000`
  Frontend: open `frontend/index.html` directly or serve `frontend/`
  with any static file server

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
|- frontend/
|  |- index.html
|  |- search.html
|  |- css/
|  |  `- style.css
|  `- js/
|     |- config.js
|     `- app.js
|- requirements.txt
|- .env.example
|- .gitignore
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
- Frontend is implemented as static HTML/CSS/JS with no build step
- Keep shared dependencies pinned in `requirements.txt` when a version
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
Phase 1 - In Development
- Backend query pipeline is implemented under `api/`
- All user queries are corpus-grounded through the same retrieval path;
  there is no direct conceptual LLM-only route
- Full prompt inspection is lazy-loaded through a dedicated backend
  endpoint; search results stay excerpt-based
- Corpus architecture is organized around a staged local workflow:
  fetch, convert, audit, normalize, discover taxonomy, classify, ingest
- `corpus/fetch_corpus.py` is implemented as an acquisition-only raw snapshot stage
- `corpus/convert_sources.py` is implemented as a structural conversion stage
- `corpus/audit_corpus.py` is implemented as a read-only canonical corpus quality analysis stage
- `corpus/normalize_corpus.py` is implemented as a deterministic provenance-preserving cleanup stage
- `corpus/discover_taxonomy.py` is implemented as an LLM-assisted, source-aware, stratified iterative taxonomy proposal stage
- `corpus/corpus_sampling.py` centralizes the deterministic source-aware stratified sampling logic shared by discovery and experiments
- `corpus/classify_corpus.py` is implemented as a corpus-wide taxonomy application stage that produces the final `data/corpus/classified.jsonl` corpus with subtechniques removed and preserves `data/corpus/classified_with_subtechniques.jsonl` as an archive copy
- `corpus/ingest.py` directly consumes finalized `data/corpus/classified.jsonl` artifacts for embedding into Qdrant
- Prompt text lives in the `TextNode` body; metadata stores only `source`, `technique`, and `prompt_id`
- `requirements.txt` now pins `fastembed==0.8.0`, the same verified
  version used successfully in both local Windows development and the
  Hetzner production server on Python 3.12 Linux
- Frontend assets are implemented under `frontend/`
- `frontend/index.html` now renders the responsible-use gate with local-storage acknowledgment persistence
- `frontend/search.html` now renders the main research interface with a glass sidebar, live stats bar, search/browse mode controls, and result panels
- `frontend/js/config.js` remains the only source of `API_BASE_URL`
- `frontend/js/app.js` owns all workspace behavior in plain JavaScript
- Search mode calls `POST /api/query` and renders an AI summary card plus excerpt-based result cards with confidence signals
- Browse mode is wired for cursor-based `GET /api/browse` pagination and renders raw corpus cards without AI summary or confidence scoring
- Full prompt inspection remains lazy-loaded through the modal flow backed by `GET /api/prompts/{prompt_id}`
- Gate and workspace visuals now follow the Stitch "Obsidian Crimson" dark glass system adapted to RedLib's zero-radius constraints
- The frontend design system is now documented in `docs/DESIGN.md` as the living baseline for future UI work
