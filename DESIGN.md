# RedLib - Design System

## Philosophy
RedLib is a practitioner tool for AI safety researchers and red teamers.
The interface should feel precise, dense, and operational rather than
consumer-polished. Visual emphasis supports evidence review: search,
attribution, confidence, and source inspection. The UI should stay
scan-friendly by default and reveal heavier detail only after explicit
user actions.

---

## Color Palette
Use the current frontend CSS tokens as the source of truth.

| Token | Hex | Role |
|-------|-----|------|
| `surface` | `#131313` | Page background |
| `surface-container-low` | `#1c1b1b` | Cards, modal shell |
| `surface-container` | `#201f1f` | Input and prompt boxes |
| `surface-container-high` | `#2a2a2a` | Hover and skeleton states |
| `surface-container-highest` | `#353534` | Inactive badges |
| `primary` | `#e50914` | Accent, active states, action links |
| `primary-dark` | `#c0000c` | Hover state for primary actions |
| `on-primary` | `#fff7f6` | Text on red backgrounds |
| `on-surface` | `#e5e2e1` | Primary text |
| `on-surface-variant` | `#e9bcb6` | Secondary text and metadata |
| `outline-variant` | `#5e3f3b` | Borders and dividers |
| `outline` | `#af8782` | Stronger outline state |
| `secondary` | `#64de8d` | High confidence |
| `tertiary` | `#ffb960` | Medium confidence |

### Usage Rules
- Use red only for accents, active states, tags, action links, borders
  on focus, and primary buttons.
- Do not use red for long-form body copy.
- Confidence colors stay semantic: green for `HIGH`, amber for `MED`,
  muted neutral for `LOW`.

---

## Typography
The frontend uses two families only.

| Token | Font | Role |
|-------|------|------|
| `headline` | IBM Plex Mono | Wordmark, numbers, labels |
| `body` | Inter | Summaries, descriptions, body text |
| `code` | IBM Plex Mono | Prompt excerpts and full prompt text |

### Font Loading
```html
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
```

### Usage Rules
- IBM Plex Mono is used for labels, tags, IDs, stats, and prompt text.
- Inter is used for summaries and general reading text.
- Section labels use small caps styling and wide tracking.

---

## Layout

### Header
- Height: `64px`
- Sticky top bar with border bottom
- Left: wordmark and red square dot
- Right: GitHub button only

### Search Interface
- Two-column layout on desktop: sidebar plus main content
- Sidebar lists technique filters and last sync
- Main area contains search, stats, AI summary, and result cards

### Modal
- Centered overlay
- Sharp-corner shell with red left border
- Used for explicit source inspection only

---

## Component Patterns

### Stats Bar
- Three-column grid
- Displays prompt count, source count, and last sync
- Numbers use mono styling for a telemetry feel

### Search Input
- Full-width input with inline search icon and right-aligned `Search`
  button
- Focus state uses the red border accent

### AI Summary Card
- Red left border
- Hidden until a query returns a summary
- Shows grounded synthesis only, never raw full prompts

### Result Card
- Default interaction is scan-first, not deep-read
- Cards show:
  1. technique tag, confidence, and prompt ID
  2. truncated prompt excerpt
  3. source plus explicit action link

### Result Card Action
- Label must be `View Full Prompt ->`
- Do not call this action `Detailed Report` unless a true analytic
  report view exists
- The action opens a modal and fetches the raw prompt lazily

### Prompt Excerpts
- Search results remain excerpt-based
- Excerpts are truncated and visually boxed in mono text
- Full prompt text must not be returned with every search response

### Full Prompt Modal
- Opens only after explicit user action
- Shows prompt ID, technique, full prompt body, and source
- Uses a loading state inside the prompt body area while the fetch is in
  flight
- Uses an inline error state in the same area if loading fails
- Prompt content must render as plain text, never HTML

### Confidence Indicator
- Dot plus label
- `HIGH` uses green
- `MED` uses amber
- `LOW` uses muted neutral styling

---

## Interaction Rules
- Search responses should stay lightweight and excerpt-based.
- Full prompt inspection is a second-step action.
- The modal should open immediately so the user gets fast feedback, then
  transition from loading state to loaded prompt or error message.
- Closing the modal should cancel the relevance of any in-flight fetch
  response on the frontend.

---

## Motion
- Card hover lifts slightly with a short transition.
- Search wrapper scales subtly on focus.
- Button press states should feel quick and controlled.
- Avoid decorative animation that does not support the workflow.

---

## Do's and Don'ts

DO:
- Keep sharp corners across cards, buttons, inputs, and modal shells.
- Preserve high information density while keeping sections readable.
- Keep result cards optimized for scanning, not for full prompt reading.
- Use explicit labels that match behavior.
- Show source attribution on every result card and in the full prompt
  modal.

DON'T:
- Ship full raw prompts in every search response.
- Blur the distinction between AI summary and raw source inspection.
- Use rounded, soft, or playful UI language.
- Add decorative UI that competes with evidence review.
- Label a raw prompt modal as a report or analysis view.
