# RedLib - Design System

## Current Frontend System
- Frontend runtime: Vite + React in `frontend/src/`
- Routing: React Router with `/` for the gate and `/workspace` for the
  main application
- Styling approach: custom CSS in `frontend/src/index.css`
- Data policy: all UI data is fetched from the live backend API through
  `frontend/src/config.js`
- Interaction model: responsible-use gate -> sticky research workspace
  -> semantic search or raw corpus browse -> lazy full-prompt modal

## Visual Direction
- Aesthetic: Resend-inspired premium dark interface adapted to RedLib's
  safety-research context
- Background: pure black `#000000`
- Surface hierarchy:
  - `#0f0f0f` for primary panels and cards
  - `#111111` for raised surfaces such as stat cells and controls
  - `#151515` for hover lift states only
- Depth model:
  - no shadows
  - borders and near-black surface shifts create separation
  - soft radial red glow is reserved for the gate corpus stat and the
    Total Prompts stat
- Shape language: zero border radius across the entire interface
- Mood: editorial, deliberate, severe, and research-grade rather than
  glossy SaaS

## Color System
- `--bg`: `#000000`
- `--surface`: `#0f0f0f`
- `--surface-2`: `#111111`
- `--surface-3`: `#151515`
- `--line`: `rgba(255,255,255,0.06)`
- `--line-strong`: `rgba(255,255,255,0.12)`
- `--text`: `#ffffff`
- `--muted`: `#666666`
- `--muted-strong`: `#909090`
- `--accent`: `#e50914`
- `--accent-soft`: `rgba(229,9,20,0.18)`
- `--success`: `#5ee287`
- `--warning`: `#ffbd59`
- `--low`: `#777777`
- `--overlay`: `rgba(0,0,0,0.8)`

Usage rules:
- White carries all primary hierarchy and large numbers
- `#666666` carries secondary copy and labels
- Red appears sparingly: gate glow, stat glow, active borders, prompt
  action links, and technique tags
- Technique tags use a dark fill, soft red border, and red text
- Confidence states are dot-based only:
  - HIGH: green glow
  - MED: amber glow
  - LOW: muted gray

## Typography
- Display face: `Instrument Serif`
- UI/body face: `Inter`
- Mono/data face: `IBM Plex Mono`

Type hierarchy:
- Gate headline:
  - `clamp(3rem, 7vw, 5rem)`
  - `Instrument Serif`
  - tight editorial leading
- Stat numerals:
  - `clamp(2.1rem, 4vw, 3.5rem)` in the workspace
  - `clamp(2.8rem, 6vw, 4.75rem)` in the gate
  - white, bold, tabular
- Body copy:
  - `Inter`
  - muted white or white depending on emphasis
- Labels, IDs, sources, and tags:
  - `IBM Plex Mono`
  - muted or red based on purpose

Typography behavior:
- Display typography is reserved for the gate only
- Workspace headings avoid hero theatrics and stay compact
- Long prompt text is rendered as plain text in mono inside the modal

## Spacing Scale
- `--space-1`: `0.5rem`
- `--space-2`: `0.75rem`
- `--space-3`: `1rem`
- `--space-4`: `1.5rem`
- `--space-5`: `2rem`
- `--space-6`: `3rem`
- `--space-7`: `4rem`

Layout rhythm:
- Panels and cards use generous internal padding around `1.4rem` to
  `1.75rem`
- The main workspace uses a 240px left rail and a fluid right column
- Section spacing is intentionally open so the interface never feels
  cramped

## Component Patterns

### Responsible Use Gate
- Full-screen black field
- Centered single panel with subtle border
- Large serif headline
- Live corpus stat fetched from `/api/stats`
- Three condition lines with no bullets
- Checkbox acknowledgment persisted in local storage
- Entry button remains dark until hovered

### Header
- Sticky black bar
- Bottom border only
- White `RedLib` wordmark with a small red dot
- Single GitHub action on the right

### Stats Bar
- Three equal-width stat cells
- Pure border-based separation
- Large white numerals and muted labels
- Only Total Prompts gets the red glow treatment

### Technique Rail
- Fixed-width left sidebar on desktop
- Small-caps muted section label
- Eight categories listed as sharp, minimal buttons
- Active state uses a 1px red left border
- Count badges animate from zero on load
- Loading state uses skeleton pulses on badge slots

### Search and Browse Controls
- Search/Browse mode toggle uses a subtle bottom-border treatment
- Search input is full-width, dark, and gains a restrained red focus glow
- Mode explanation stays one sentence and updates by workflow

### Search Results
- AI summary card appears first and uses a red-accented edge treatment
- Result cards show:
  - technique tag
  - confidence dot and label
  - source attribution
  - excerpt only
  - `View Full Prompt →` action

### Browse Results
- Same card shell as search results
- Confidence row removed
- Source attribution retained on every card
- Pagination remains explicit through `Load more`

### Full Prompt Modal
- Black overlay at `rgba(0,0,0,0.8)`
- Centered near-black panel with sharp edges and subtle border
- Header includes prompt ID, technique tag, and close action
- Prompt body is scrollable, mono, and always plain text
- Footer preserves source attribution
- Loading and error states remain inline inside the content area

## Motion Rules
- Transitions stay within 150ms to 200ms
- Hover states rely on subtle surface lift and border brightening
- Search input focus adds a restrained red glow
- Count-up animation duration is 1000ms
- Skeleton loading uses a soft pulse only
- Reduced motion disables animation and compresses transition timing to
  near-zero

## Responsive Behavior
- Desktop:
  - sticky header
  - 240px left technique rail
  - flexible right results workspace
- Tablet:
  - sidebar stacks above results
  - stat cells stay readable without changing the visual language
- Mobile:
  - single-column layout
  - stacked search input and button
  - modal and result metadata collapse vertically without changing the
    hard-edged system

## Resend-Inspired Decisions
- Pure black background instead of charcoal
- Near-black panel separation instead of obvious contrast blocks
- Invisible-feeling borders that define structure without adding visual
  noise
- Accent color used as atmosphere and signal, not as paint
- Editorial headline voice combined with clean product UI typography
- No decorative shadows, pills, or soft corners
