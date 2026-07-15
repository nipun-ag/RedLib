# RedLib - Design System

## Current Frontend System
- Frontend runtime: Vite + React in `frontend/src/`
- Styling approach: Tailwind entrypoint plus custom CSS in
  `frontend/src/index.css`
- API base URL source: `frontend/src/config.js` only
- Layout model: responsible-use gate -> compact workspace header ->
  shared search/browse workbench -> results and inspection panels

## Visual Direction
- Theme: dark tactical editorial interface
- Shape language: sharp corners everywhere
- Surface hierarchy:
  - `--bg` for the page field
  - `--bg-raised` for the taxonomy rail
  - `--bg-panel` and `--bg-panel-2` for active tool surfaces
  - `--bg-panel-3` reserved for stronger emphasis states
- Accent strategy:
  - red draws attention to primary actions, active filters, and key
    summary states
  - blue signal color supports data chips and quieter interface cues
- Copy strategy:
  - minimal, operator-facing, and tool-oriented
  - no long explanatory interface prose inside the workspace

## Typography
- Body stack:
  - `Aptos`, `Segoe UI Variable Text`, `Segoe UI`, `Inter`, sans-serif
- Display stack:
  - `Bahnschrift`, `DIN Alternate`, `Arial Narrow`, `Inter`, sans-serif
- Mono/data stack:
  - `IBM Plex Mono`, `Consolas`, monospace

Hierarchy rules:
- Product title is short, uppercase, and compact rather than hero-sized
- Technique names use the display stack for a more deliberate editorial
  voice
- Labels, mode toggles, stats, IDs, and counts use mono with tighter
  uppercase tracking
- Body copy stays muted and short

## Layout Proportions
- Header is intentionally compressed so users reach the tool quickly
- Stats sit beside the title instead of below a long hero block
- Sidebar opens directly into category filters with no narrative copy
- Mode explainer is a single sentence only
- Results remain the dominant visual surface

## Component Behavior
- Responsible-use gate remains in place
- SEARCH MODE / BROWSE MODE toggle remains in place
- Search mode:
  - query input
  - optional category filter
  - AI summary above result cards
  - technique mix in the side panel
- Browse mode:
  - category-first flow
  - raw excerpt cards
  - cursor pagination with `Load More`
- Full prompt inspection:
  - lazy modal only
  - action label stays exactly `View Full Prompt`
  - prompt text renders as plain text

## State Design
- Loading states use muted copy and a small blue pulse indicator
- Stats never show harsh broken-language placeholders
- Error states use calm connection language instead of alarming failure
  language when possible
- Empty states are short and directional

## Color Tokens
- `--bg`: `#091017`
- `--bg-raised`: `#0f1922`
- `--bg-panel`: `#15212b`
- `--bg-panel-2`: `#1b2834`
- `--bg-panel-3`: `#243342`
- `--line`: `#304150`
- `--line-strong`: `#486175`
- `--text`: `#f2f5f7`
- `--text-muted`: `#b2c0cb`
- `--text-dim`: `#7f93a3`
- `--accent`: `#f34b3f`
- `--accent-soft`: `rgba(243, 75, 63, 0.16)`
- `--accent-line`: `rgba(243, 75, 63, 0.42)`
- `--signal`: `#a8cdff`
- `--signal-soft`: `rgba(168, 205, 255, 0.16)`
- `--ok`: `#9fe870`
- `--warn`: `#ffd36c`
- `--danger`: `#ff7b72`

## Motion Rules
- Keep motion short and functional
- Category counts still use count-up animation
- Buttons keep subtle press feedback
- Reduced motion disables transitions and animation globally

## Responsive Behavior
- Desktop:
  - left taxonomy rail
  - right workbench
  - side analysis panel
- Tablet:
  - stacked content areas
  - same typographic hierarchy
- Mobile:
  - collapsible filter rail
  - full-width primary controls
  - compact header and tool rhythm preserved
