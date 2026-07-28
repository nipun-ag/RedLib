# RedLib

## Agent Hub
All skills, tools, and MCP servers live at `C:/Users/nipun/.ai/`.
Never create or install skills, tools, or MCP configs at the project level — look there first for any capability.
Chain: this file → `~/.claude/CLAUDE.md` → `C:/Users/nipun/.ai/AGENTS.md`

AI safety research tool — adversarial jailbreak corpus with RAG-powered search and synthesis.
Live at `https://redlib.bynipun.com` · API at `https://api-redlib.bynipun.com`

## Project context

Read `PRODUCT.md` for positioning, users, and design principles.
Read `docs/ARCHITECTURE.md` for system design.
Read `docs/DESIGN.md` for the Ink & Platinum design spec and token system.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19, Vite, TypeScript, Tailwind CSS v4, shadcn/ui |
| Backend | FastAPI on Hetzner (systemd service `redlib`) |
| RAG | LlamaIndex + Qdrant Cloud |
| Embeddings | OpenAI `text-embedding-3-small` |
| Reranking | Cohere Rerank |
| Synthesis | Anthropic Claude Haiku 4.5 |
| Secrets | Doppler |
| Frontend deploy | Vercel |

## Key files

- `api/app.py` — FastAPI routes
- `api/rag.py` — query pipeline
- `frontend/src/pages/WorkspacePage.tsx` — main workspace UI
- `frontend/src/pages/GatePage.tsx` — responsible-use gate
- `frontend/src/lib/taxonomy.ts` — category labels, localStorage gate key

## Demo video

Recording scripts live in `demo/scripts/`. All 4 clips import from the global playwright core.
Run with: `node demo/scripts/run_all.js`
See `demo/scripts/clip_*.js` for individual clips.

## localStorage gate key

`redlib.researchGateAcknowledged` — set to `"true"` via `addInitScript()` to bypass gate in scripts.

---

← Agent config: `~/.claude/CLAUDE.md`
← Global hub: `C:/Users/nipun/.ai/AGENTS.md`
