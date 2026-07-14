# RedLib - Design System

## Design Intent
RedLib's frontend should feel like a research terminal for practitioners,
not a polished consumer SaaS dashboard. The UI is dark, dense, sharply
bounded, and operational. It prioritizes scan speed, source visibility,
and clear mode state over decorative flourish.

The visual direction is tactical telemetry rather than marketing polish:
- dark-only presentation
- rigid grid and hard 90-degree corners
- monospace used for IDs, counts, prompt text, tags, and system labels
- restrained red accent used for state, emphasis, and corpus alerts
- high information density with readable spacing, not cramped clutter

## Color Tokens
Use these tokens exactly in frontend work unless a later approved design
revision replaces them:

| Token | Hex | Role |
| --- | --- | --- |
| Background | `#131313` | Global canvas |
| Cards / Modal | `#1c1b1b` | Primary surfaces |
| Input Boxes | `#201f1f` | Inputs and inset panels |
| Hover States | `#2a2a2a` | Hovered list items and buttons |
| Inactive Badges | `#353534` | Placeholder / inactive badges |
| Primary Accent | `#e50914` | Search mode emphasis, alerts, active borders |
| Primary Hover | `#c0000c` | Hovered accent controls |
| Text On Red | `#fff7f6` | Accent button text |
| Primary Text | `#e5e2e1` | Main content text |
| Secondary Text / Metadata | `#e9bcb6` | Labels, metadata, helper copy |
| Borders / Dividers | `#5e3f3b` | Structural rules |
| Strong Outline | `#af8782` | Active hover/focus outline |
| High Confidence | `#64de8d` | HIGH confidence dot |
| Medium Confidence | `#ffb960` | MED confidence dot |
| Low Confidence | `#7d6865` | LOW confidence dot |

Additional surface rules:
- Never use pure black.
- Never introduce purple, blue neon, or multi-accent gradients.
- Red is the only accent family for interaction and emphasis.
- Background texture may be subtle scanline or grid treatment, but it
  must stay low-contrast and never compete with content.

## Typography
Load typography from Google Fonts:
- `IBM Plex Mono` weights `400, 500, 600, 700`
- `Inter` weights `400, 500, 600`

Usage rules:
- `IBM Plex Mono`:
  - all numbers and counts
  - technique badges
  - IDs
  - prompt excerpts and full prompt text
  - status labels, metadata rows, wordmark, and mode badges
- `Inter`:
  - summaries
  - explanatory copy
  - longer body text
  - category names

Type behavior:
- Headings stay compact and heavy, with tight tracking.
- Body copy should remain readable at dense line lengths.
- Prompt text must preserve plaintext formatting and use monospace.
- Avoid oversized hero-style typography in the application surface.

## Layout
### Global shell
- Sticky top header at `64px` height.
- Header layout:
  - RedLib wordmark left
  - GitHub link right
- Main desktop layout:
  - left sidebar at roughly `320px`
  - right content column fluid
- Mobile layout:
  - single column
  - sidebar collapses behind a toggle

### Sidebar
The sidebar exists to support fast narrowing of the corpus:
- technique category list
- live category counts
- corpus total
- last sync date
- clear filter action

Behavior:
- category labels render immediately from a static ordered taxonomy list
- count badges begin as `...`
- counts hydrate asynchronously from `/api/categories`
- categories with `0` count hide after hydration
- active category should be visually obvious

### Main panel
The right column contains:
- active mode strip
- mode explainer
- search input and action
- current category filter badge
- shared result area

There is one result area for both modes. The mode changes, not the
layout.

## Interaction Model
### Responsible use gate
`frontend/index.html` is a minimal gate, not a legal wall:
- short framing copy
- one clear `I understand` button
- dark surface with red left border
- acknowledgment stores in `sessionStorage`
- confirmation navigates to `search.html`

### Search mode
Triggered by:
- typing a query and pressing Search
- clicking a category while a query is already present

Behavior:
- POST `/api/query` with `{ query, category_filter }`
- show AI summary card first
- show result cards below
- include confidence indicator and numeric score
- update active mode label to `Search`
- mode explainer must state that AI search is being used

Search result card structure:
- technique badge
- confidence chip with colored dot
- prompt excerpt only, never full prompt
- source
- prompt ID
- `View Full Prompt ->` action

### Browse mode
Triggered by:
- clicking a category when no query is typed

Behavior:
- GET `/api/browse?category=...&cursor=...&limit=20`
- no AI summary card
- raw prompt cards only
- load-more pagination using `next_cursor`
- update active mode label to `Browse`
- mode explainer must state there is no AI involved

Browse card structure:
- technique badge
- prompt excerpt
- source
- prompt ID
- `View Full Prompt ->` action

### Full prompt modal
The full prompt stays lazy-loaded:
- open on `View Full Prompt ->`
- immediately show loading state
- fetch `GET /api/prompts/{prompt_id}`
- render plain text only, never HTML
- show prompt ID, technique, and source
- use the same dark surface language with a red left border

### Loading and failure states
- category counts may fail independently without blocking labels
- search failures should keep the surface readable and explain backend reachability
- browse failures should clearly state that `/api/browse` is expected but unavailable
- modal failures should not leave stale prompt text visible

## Component Patterns
### Header
- sticky
- hard bottom border
- no rounded pills
- compact mono branding

### Buttons
- sharp corners only
- solid red for primary actions
- dark inset surfaces for secondary actions
- hover darkens or outlines, never glows
- active press feedback is subtle translate/lift only

### Inputs
- dark inset background
- border in `#5e3f3b`
- focus state uses red border accent
- no rounded corners

### Technique badges
- monospace
- uppercase
- red bordered by default
- inactive state uses `#353534`

### Result cards
- single hard-edged surface
- no nested card stacks
- metadata line at bottom
- subtle hover lift only
- source attribution always visible

### AI summary card
- same base surface as cards
- red left border
- concise analytical copy

### Status banners
- compact monochrome system rows
- optional left rule for info vs error emphasis

### Confidence indicator
- textual label plus dot
- green for HIGH
- amber for MED
- muted gray-brown for LOW

## Motion Rules
Motion is restrained and functional:
- no decorative looping animation
- no bounce or elastic behavior
- only fast hover, active, modal, and state transitions
- use transform/background/border transitions only
- support `prefers-reduced-motion: reduce`

Approved motion:
- slight card lift on hover
- slight button press feedback
- standard modal open/close without theatrical staging

Disallowed motion:
- ambient drifting objects
- celebratory transitions
- auto-playing list reveals
- large parallax or hero animation

## Content and Tone
UI copy should match RedLib's product voice:
- precise
- analytical
- direct
- non-marketing
- practitioner-facing

Avoid:
- consumer onboarding language
- promotional filler
- vague category labels
- modal titles like `Detailed Report`

## Responsive Rules
- Below desktop, collapse to one column.
- Sidebar becomes toggleable instead of sticky.
- Search form stacks vertically on smaller widths.
- Modal metadata collapses to a single column.
- Dense presentation should remain intact, but tap targets still need
  usable spacing.

## Implementation Notes
- Frontend stays static: HTML, CSS, JS only.
- No build step.
- API base URL lives only in `frontend/js/config.js`.
- `search.html` assumes:
  - `/api/query` exists now
  - `/api/categories` exists now
  - `/api/prompts/{prompt_id}` exists now
  - `/api/stats` exists now
  - `/api/browse` will exist with the documented cursor contract

## Design Anti-Patterns
Do not introduce these without a deliberate design rewrite:
- rounded corners anywhere
- purple or blue AI gradients
- consumer dashboard aesthetics
- thick glassmorphism
- hidden source attribution
- full prompt text in search result cards
- decorative icon clutter
- multi-accent palettes
- soft card-on-card nesting
