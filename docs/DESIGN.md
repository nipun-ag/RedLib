# RedLib - Design System

## Current Frontend System
- Frontend runtime: Vite + React in `frontend/src/`
- Styling approach: Tailwind entrypoint plus custom CSS in
  `frontend/src/index.css`
- API base URL source: `frontend/src/config.js` only
- Layout model: responsible-use gate -> single research workspace ->
  search or browse mode within the same shell

## Visual Direction
- Theme: dark-only tactical editorial interface
- Shape language: hard edges only, zero rounded corners anywhere
- Surface behavior: layered steel-blue panels over a near-black field
- Mood: operational, research-first, source-grounded, not consumer SaaS
- Motion: restrained and functional
  - category counts animate in with count-up motion
  - buttons use short press feedback
  - no decorative looping motion outside loading feedback

## Color System
- `--bg`: `#090d11`
- `--bg-raised`: `#10161c`
- `--bg-panel`: `#131b22`
- `--bg-panel-2`: `#18212a`
- `--bg-panel-3`: `#202b35`
- `--line`: `#2c3a46`
- `--line-strong`: `#43576a`
- `--text`: `#ebf0f4`
- `--text-muted`: `#91a3b4`
- `--text-dim`: `#6a7b8b`
- `--accent`: `#f34b3f`
- `--accent-soft`: `rgba(243, 75, 63, 0.12)`
- `--accent-line`: `rgba(243, 75, 63, 0.32)`
- `--signal`: `#9cc3ff`
- `--signal-soft`: `rgba(156, 195, 255, 0.14)`
- `--ok`: `#9fe870`
- `--warn`: `#ffd36c`
- `--danger`: `#ff7b72`

## Typography
- Primary voice: modern sans serif stack led by `Inter`
- Secondary/system voice: monospace stack led by `IBM Plex Mono`
- Headline behavior:
  - uppercase
  - tight tracking
  - short line lengths
  - large editorial scale without oversized hero sprawl
- Supporting copy behavior:
  - muted blue-gray tone
  - comfortable line height
  - max-width control for long explanatory text
- Numeric behavior:
  - monospace
  - tabular feel for counts, scores, and stats

## Layout Structure
- Responsible-use gate:
  - split-screen composition
  - left side explains corpus purpose
  - right side sets access conditions and acknowledgement
- Main app shell:
  - header with product framing and corpus stats
  - left taxonomy rail for technique filters
  - right workbench for mode controls, query input, explainer, and results
- Result area:
  - primary column for summary and result cards
  - secondary column for technique mix or inspection guidance
- Full prompt inspection:
  - modal overlay only
  - loaded lazily after explicit action

## Component Rules
- Every result card must show source attribution
- Search result cards only show `prompt_excerpt`, never full prompt text
- Full prompt CTA label is exactly `View Full Prompt`
- Prompt bodies render as plain text with preserved whitespace
- Category counts stay live and animated from `/api/categories`
- Mode explainer changes based on:
  - idle search
  - active search
  - active browse
  - category selection

## Interaction Model
- Search Mode:
  - semantic query input
  - optional technique filter from the left rail
  - AI summary shown above excerpt cards
  - technique breakdown shown in the side panel
- Browse Mode:
  - category-first workflow
  - raw corpus excerpts only
  - cursor pagination with `Load More`
  - no answer synthesis panel
- Responsible-use acknowledgement:
  - session-scoped
  - stored in browser session storage

## Motion Rules
- Count-up animation duration: short, under one second
- Press feedback: subtle scale-down only
- Loading feedback: single pulsing square indicator
- Reduced motion:
  - all transitions collapse when `prefers-reduced-motion: reduce`
  - no layout-dependent reveal sequences

## Responsive Behavior
- Desktop:
  - two-column workspace with persistent taxonomy rail
- Tablet:
  - stacked content sections with the same visual language
- Mobile:
  - taxonomy rail can collapse
  - mode buttons and primary actions become full-width
  - header stats stack vertically

## File Ownership
- `frontend/src/pages/ResearchPage.jsx`
  - page orchestration and state handoff
- `frontend/src/components/`
  - reusable UI surfaces
- `frontend/src/hooks/`
  - API and interaction state
- `frontend/src/lib/formatters.js`
  - display helpers
- `frontend/src/index.css`
  - visual system, layout, and interaction styling
