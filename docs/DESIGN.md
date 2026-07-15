# RedLib - Design System

## Current Frontend System
- Runtime: static HTML, CSS, and JavaScript under `frontend/`
- Entry pages:
  - `frontend/index.html` for the responsible-use gate
  - `frontend/search.html` for the research workspace
- Shared styling: `frontend/css/style.css`
- Shared API base: `frontend/js/config.js`
- Workspace logic: `frontend/js/app.js`
- Delivery model: pages work when opened directly from disk or served by
  a static file server

## Design Direction
- Visual source: Stitch "Obsidian Crimson" references for the gate and
  workspace
- Mood: technical elegance with deep charcoal layering, subtle crimson
  lighting, and frosted glass surfaces
- Interaction style: restrained but tactile, with smooth lift
  transitions, soft hover halos, and narrow monospace metadata details
- Shape override: unlike the Stitch defaults, RedLib now enforces zero
  border radius everywhere

## Core Tokens

### Fonts
- Display: `Hanken Grotesk`
- Body: `Inter`
- Code and labels: `JetBrains Mono`

### Color Tokens
These are defined as CSS custom properties in `frontend/css/style.css`
using the Stitch palette values:

- `--surface`: `#121317`
- `--surface-dim`: `#121317`
- `--surface-bright`: `#38393d`
- `--surface-container-lowest`: `#0d0e12`
- `--surface-container-low`: `#1a1b1f`
- `--surface-container`: `#1e1f23`
- `--surface-container-high`: `#292a2e`
- `--surface-container-highest`: `#343539`
- `--surface-variant`: `#343539`
- `--on-surface`: `#e3e2e7`
- `--on-surface-variant`: `#e7bdb7`
- `--inverse-surface`: `#e3e2e7`
- `--inverse-on-surface`: `#2f3034`
- `--outline`: `#ad8883`
- `--outline-variant`: `#5d3f3b`
- `--surface-tint`: `#ffb4aa`
- `--primary`: `#ffb4aa`
- `--primary-container`: `#ff5545`
- `--on-primary`: `#690003`
- `--on-primary-container`: `#5c0002`
- `--inverse-primary`: `#c0000a`
- `--secondary`: `#c8c6c5`
- `--on-secondary`: `#313030`
- `--secondary-container`: `#474746`
- `--on-secondary-container`: `#b7b5b4`
- `--tertiary`: `#c8c6c8`
- `--on-tertiary`: `#303032`
- `--tertiary-container`: `#919092`
- `--on-tertiary-container`: `#29292b`
- `--error`: `#ffb4ab`
- `--on-error`: `#690005`
- `--error-container`: `#93000a`
- `--on-error-container`: `#ffdad6`

### Semantic UI Tokens
- `--glass-surface`: translucent charcoal for floating panels
- `--glass-surface-strong`: denser modal-grade glass background
- `--glass-border`: low-opacity white border used on glass layers
- `--obsidian-surface`: layered panel gradient used by the gate card
- `--green-confidence`: HIGH confidence dot
- `--amber-confidence`: MED confidence dot
- `--muted-confidence`: LOW confidence dot

## Typography Scale
- Display large:
  - 48px / 56px desktop
  - 36px / 42px mobile
  - tracking `-0.02em`
- Headline medium:
  - 24px / 32px
- Body large:
  - 18px / 28px
- Body medium:
  - 16px / 24px
- Label small:
  - 12px / 16px
  - tracked out uppercase mono for metadata

Usage rules:
- Hanken Grotesk is reserved for major product headings, key numeric
  stats, and high-level titles
- Inter carries all explanatory copy and prompt excerpts
- JetBrains Mono is used for IDs, tags, labels, counts, and control
  accents

## Spacing System
- `--space-base`: `4px`
- `--space-xs`: `8px`
- `--space-sm`: `16px`
- `--space-md`: `24px`
- `--space-lg`: `48px`
- `--space-xl`: `80px`
- `--space-gutter`: `24px`
- `--margin-mobile`: `16px`
- `--margin-desktop`: `64px`

Layout behavior:
- Desktop workspace uses a fixed left rail and a flexible main column
- Panels breathe with 24px to 32px internal padding
- Vertical spacing stays generous to preserve the luxury technical feel

## Effects and Surfaces

### `.glass-panel`
- Semi-transparent charcoal panel
- `backdrop-filter: blur(12px)`
- 1px low-opacity white border
- subtle inset highlight

### `.obsidian-card`
- Gate-specific elevated panel
- dark layered gradient
- frosted blur
- soft black depth shadow plus inner highlight

### Ambient orbs
- Fixed radial crimson glows in opposing corners
- used to create depth behind both pages without adding clutter

### Crimson glow buttons
- Primary action style
- red gradient fill
- soft outer crimson halo
- slightly stronger glow and upward lift on hover

### Hover lift
- Cards and stats move upward by 4px on hover
- transitions use the slower premium motion curve rather than instant
  hover jumps

## Motion
- Standard easing: `cubic-bezier(0.4, 0, 0.2, 1)`
- Lift easing: `cubic-bezier(0.16, 1, 0.3, 1)`
- Fast transition: 180ms
- Medium transition: 300ms
- Lift transition: 400ms
- Skeleton shimmer uses a linear pass across the surface

## Scrollbars
- Thin custom dark scrollbar
- transparent track
- dark thumb at rest
- primary-tinted thumb on hover

## Page Patterns

### Responsible Use Gate
- Centered obsidian card over atmospheric orbs
- RedLib wordmark with security icon
- headline: "Secure Access to Adversarial Intelligence"
- live corpus stat from `/api/stats`, with fallback to `168,115`
- numbered condition list
- checkbox acknowledgment stored in local storage
- gated navigation into `search.html`

### Research Workspace
- Left sidebar converted fully into technique filters
- Glass header with RedLib wordmark and GitHub link only
- Top stats bar:
  - Total Prompts
  - Sources
  - Last Sync
- Search/Browse toggle above the search input
- AI summary card with red left border treatment
- Result cards with:
  - technique tag
  - confidence dot and label in search mode only
  - source attribution
  - excerpt-only body
  - `View Full Prompt →` action

### Full Prompt Modal
- backdrop blur and dark overlay
- prompt ID in mono
- technique tag in the header
- plain-text full prompt inside a scrollable `pre`
- source attribution footer
- lazy fetch and inline error/loading states

## Behavioral Rules
- No rounded corners anywhere
- No framework runtime or build step
- All live data comes from the FastAPI API
- Prompt excerpts only in result cards
- Full prompt text only inside the modal
- `API_BASE_URL` is sourced only from `frontend/js/config.js`
