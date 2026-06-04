# RedLib — Progress Log

## Deferred Features
These were discussed during planning and deliberately excluded
from Phase 1. Revisit after the core pipeline is working.

- User submissions / community-contributed prompts
  (requires moderation pipeline, validation, spam handling)
- Detailed Report page per prompt
  (wire "DETAILED REPORT →" to a modal in Phase 1 instead)
- Saved searches / user accounts
- Analytics dashboard (technique distribution charts, trends)
- Corpus update automation (scheduled re-ingestion)
- Export results as CSV or JSON
- API access for external developers
- Comparison mode (query two technique categories side by side)
- Target model filter (filter by GPT-4, Claude, Llama, etc.)
- Date range filter (prompts by collection period)
- Docs, Models, Safety nav pages
  (nav links removed from Phase 1 — no backing pages yet)

---

## 2026-06-04
Project initialized. Planning complete.

Stack decided:
- Frontend: Vanilla JS + HTML + CSS (Tailwind via CDN)
- Backend: FastAPI (Python)
- RAG Framework: LlamaIndex
- Vector DB: Pinecone (hybrid dense + sparse)
- Embeddings: OpenAI text-embedding-3-small
- Reranking: Cohere Rerank API
- LLM: Anthropic Claude Haiku 4.5
- Evaluation: RAGAS
- Hosting: Hetzner VPS
- Deploy: GitHub Actions

Design locked from Google Stitch (two screens: landing + search
interface). Netflix red (#e50914) and black (#131313) palette.
IBM Plex Mono + Inter typography.

All six documentation files generated. Ready to start Phase 1.
