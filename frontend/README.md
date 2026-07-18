# RedLib Frontend

React + Vite research UI for RedLib.

## Design System

The implemented Ink & Platinum visual and interaction specification lives in
[`../docs/DESIGN.md`](../docs/DESIGN.md). Keep frontend changes aligned with
its tokens, component states, responsive behavior, accessibility rules, and
canonical-to-display taxonomy boundary.

## Source Layout

```text
src/
|- pages/          # GatePage, WorkspacePage
|- components/     # Workspace composition + LiquidAtmosphere
|- components/ui/  # shadcn/Radix primitives
`- lib/            # api.ts client, taxonomy.ts helpers, utils.ts
```

Routes:

- `/` responsible-use gate
- `/workspace` research workspace
- `/search.html` → `/workspace`
- `/index.html` and unknown routes → `/`

## Scripts

```bash
npm install
npm run dev      # http://localhost:3000 with /api proxy
npm run build    # production build to dist/
npm run lint     # oxlint
npm run preview  # preview the production build
```

## Environment

Optional `VITE_API_BASE_URL`:

- unset in local dev → same-origin `/api` via Vite proxy
- unset in production build → `https://api-redlib.bynipun.com`
- set explicitly to override either case

API access belongs in `src/lib/api.ts`. Taxonomy display aliases, category
descriptions, fallback counts, gate persistence, and corpus-source provenance
belong in `src/lib/taxonomy.ts`.

## Gate and Fallback Behavior

- Gate acknowledgment is stored in `localStorage` as
  `redlib.researchGateAcknowledged`
- Previously acknowledged users skip the gate and land on `/workspace`
- Direct `/workspace` access without acknowledgment redirects to `/`
- Gate stats failures fall back to `168,115` prompts
- Workspace stats failures render `—`
- Category-loading failures keep the eight hardcoded fallback families/counts
- Search and browse keep independent loading, error, empty, and pagination
  states; there is no retry control yet

## Vercel

- Root Directory: `frontend`
- Build Command: `npm run build`
- Output Directory: `dist`
- SPA rewrites: `vercel.json`
