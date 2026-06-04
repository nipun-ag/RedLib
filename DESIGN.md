# RedLib — Design System

## Philosophy
RedLib is a practitioner tool for AI safety researchers and red teamers.
The design language is precise, dense, and functional — a security
research interface, not a SaaS product. Netflix-inspired red and black
palette. IBM Plex Mono for all data and labels. Inter for body text.
Generous whitespace so nothing feels cramped. Every element earns its
place by serving the workflow.

---

## Color Palette
Extracted directly from Stitch source. Use these exact hex values.

| Token                      | Hex       | Role                                      |
|----------------------------|-----------|-------------------------------------------|
| surface                    | #131313   | Page background, body bg                 |
| surface-dim                | #131313   | Same as surface (alias)                  |
| surface-container-lowest   | #0e0e0e   | Deepest surface (scrollbar track)        |
| surface-container-low      | #1c1b1b   | Cards, disclaimer box, result cards      |
| surface-container          | #201f1f   | Search input bg, prompt text box bg      |
| surface-container-high     | #2a2a2a   | Hover states, inactive chip bg           |
| surface-container-highest  | #353534   | Inactive count badges                    |
| surface-variant            | #353534   | Surface variant (alias)                  |
| surface-bright             | #393939   | Brightest surface level                  |
| primary-container          | #e50914   | Netflix red — primary accent             |
| inverse-primary            | #c0000c   | Darker red variant                       |
| on-primary-container       | #fff7f6   | Text on red backgrounds                  |
| on-surface                 | #e5e2e1   | Primary text                             |
| on-surface-variant         | #e9bcb6   | Secondary text, labels, metadata         |
| outline-variant            | #5e3f3b   | Borders, dividers                        |
| outline                    | #af8782   | Stronger borders (outline)               |
| secondary                  | #64de8d   | High confidence indicator (green)        |
| tertiary                   | #ffb960   | Med confidence indicator (amber)         |
| inverse-surface            | #e5e2e1   | Light surface (inverse)                  |

### Usage Rules
- Red (#e50914) is used only for: active states, accents, borders on
  focus, technique tags, AI summary border, CTA buttons, "DETAILED
  REPORT" links, and the RedLib wordmark dot
- Never use red for body text or informational content
- Confidence indicators: green (#64de8d) = HIGH, amber (#ffb960) = MED,
  muted (#e9bcb6 at low opacity) = LOW

---

## Typography
Extracted from Stitch fontFamily and fontSize config.

| Token        | Font          | Size  | Line Height | Weight | Letter Spacing | Role                        |
|--------------|---------------|-------|-------------|--------|----------------|-----------------------------|
| headline-lg  | IBM Plex Mono | 32px  | 1.2         | 600    | -0.02em        | Hero heading (landing page) |
| headline-md  | IBM Plex Mono | 24px  | 1.3         | 600    | —              | Stats numbers               |
| headline-sm  | IBM Plex Mono | 18px  | 1.4         | 500    | —              | Section headers, wordmark   |
| label-lg     | IBM Plex Mono | 14px  | 1.2         | 500    | —              | Warning title, nav items    |
| label-md     | IBM Plex Mono | 12px  | 1.2         | 500    | —              | Tags, badges, small caps    |
| body-lg      | Inter         | 18px  | 1.6         | 400    | —              | Hero subheading             |
| body-md      | Inter         | 16px  | 1.6         | 400    | —              | AI summary body, card text  |
| body-sm      | Inter         | 14px  | 1.5         | 400    | —              | Tips, metadata, source text |
| code         | IBM Plex Mono | 13px  | 1.5         | 400    | —              | Prompt text in result cards |

### Font Loading
```html
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
```

### Small Caps Pattern
Section labels (TECHNIQUES, VULNERABILITY FEED, AI SUMMARY, PROMPTS,
SOURCES, LAST SYNC) use `font-variant: small-caps` with IBM Plex Mono
label-md and `tracking-widest`.

---

## Spacing System
Extracted from Stitch spacing config.

| Token  | Value | Usage                                    |
|--------|-------|------------------------------------------|
| xs     | 4px   | Tight gaps, icon-to-text                |
| sm     | 8px   | Inner gaps, badge padding               |
| md     | 16px  | Standard padding, card inner gaps       |
| lg     | 24px  | Section padding, card padding           |
| xl     | 32px  | Page margins, section gaps              |
| xxl    | 48px  | Large vertical spacing (hero section)   |
| gutter | 24px  | Gap between sidebar and main content    |
| margin | 32px  | Page horizontal padding                 |

---

## Layout

### Page Structure
- Max content width: 1000px centered (main search interface)
- Max header width: 1440px centered (sticky header)
- Sidebar width: 240px (fixed, sticky, hidden on mobile)
- Main content: flex-1, min-width 0
- Gap between sidebar and main: 24px (gutter)
- Page padding: 32px desktop, 16px mobile

### Header
- Height: 64px
- Background: surface (#131313)
- Bottom border: 1px outline-variant (#5e3f3b)
- Sticky, z-index 50
- Left: RedLib wordmark (IBM Plex Mono bold) + red square dot (10x10px)
- Right: terminal icon + GitHub button (red bg, white text)
- No nav links (Docs, Models, Safety removed — dead links in Phase 1)

### Landing Page
- Full screen, centered content vertically and horizontally
- Blueprint grid background: 40px grid, lines at #1f1f1f
- Hero gradient: radial from center, rgba(229,9,20,0.08), interactive
  on mousemove (follows cursor)
- Max content width: 800px

### Search Interface
- Two column: 240px sidebar + flex main content
- Sidebar: sticky top 80px, full height minus header, scrollable
- Mobile: sidebar hidden, horizontal scrollable chips shown instead

---

## Component Patterns

### Header Wordmark
```
RedLib + 10x10px red square (bg-primary-container, ml-0.5 mt-1)
Font: IBM Plex Mono bold, tracking-tighter
```

### Disclaimer Box (Landing)
- Background: surface-container-low (#1c1b1b)
- Border: 1px outline-variant
- Left accent: 4px red bar (absolute positioned)
- Padding: 24px
- Border radius: none (sharp corners throughout)
- Warning icon: filled, primary-container color

### Consent Button
- Background: primary-container (#e50914)
- Text: on-primary-container (#fff7f6)
- Font: headline-sm IBM Plex Mono
- Border radius: none
- Disabled state: opacity-50 + grayscale
- Enabled only when checkbox is ticked

### Example Query Chips (Landing)
- Background: surface-container-high (#2a2a2a)
- Border: 1px outline-variant
- Font: IBM Plex Mono code (13px)
- Padding: 16px horizontal, 4px vertical
- Border radius: none
- Hover: border and text brighten to on-surface

### Sidebar Technique Row
- Padding: 12px horizontal, 10px vertical
- Font: Inter body-md (16px)
- Icon: Material Symbols Outlined, 20px
- Count badge: rounded-full, 10px font

Active state:
- Background: primary-container/10 (red tint)
- Left border: 4px primary-container (#e50914)
- Text: primary-container (#e50914)
- Badge: bg primary-container, text on-primary-container

Inactive state:
- Text: on-surface-variant (#e9bcb6)
- Badge: bg surface-container-highest, muted text
- Hover: bg surface-container-high

### Stats Bar
- Grid: 3 columns
- Background: surface-container-low
- Border: 1px outline-variant
- Padding: 24px
- Dividers between columns: 1px outline-variant (left border on col 2,3)
- Number: headline-md IBM Plex Mono (24px)
- Label: label-md 10px small-caps, muted

### Search Input
- Height: 64px
- Background: surface-container (#201f1f)
- Border: 2px outline-variant, focus → 2px primary-container
- Font: body-lg Inter (18px)
- Left: search icon (48px padding)
- Right: SEARCH button (absolute, red bg, 40px height, 16px from right)
- Focus: slight scale(1.01) on wrapper
- Border radius: none

### Collapsible Tips
- Trigger: `<details>` + `<summary>` pattern
- Background: surface-container-low
- Border: 1px outline-variant
- Arrow rotates 180° when open (transition)
- Inner grid: 2 columns on desktop
- Each tip: surface-container bg, lightbulb/filter icon in red

### AI Summary Card
- Background: surface-container-low (#1c1b1b)
- Border: 1px outline-variant on top, right, bottom
- Left border: 4px primary-container (#e50914)
- Padding: 24px
- Header: psychology_alt icon (red) + "AI SUMMARY" small-caps label-md
- Body: body-md Inter, line-height 1.6

### Result Card (Vulnerability Feed)
- Background: surface-container-low (#1c1b1b)
- Border: 1px outline-variant
- Padding: 24px
- Gap between internal sections: 16px
- Hover: translateY(-2px), border-left becomes 4px primary-container
- Transition: 75ms duration

Card anatomy top to bottom:
1. Top row: technique tag + confidence indicator + prompt ID
2. Prompt text box: surface bg, 1px border at 30% opacity, IBM Plex
   Mono 13px, line-clamp-3
3. Bottom row: SOURCE label (small-caps 11px muted) + DETAILED REPORT →
   (red, bold, small-caps)

### Technique Tag
- Border: 1px primary-container
- Text: primary-container (#e50914)
- Font: IBM Plex Mono 10px bold uppercase
- Padding: 8px horizontal, 2px vertical
- Border radius: none

### Confidence Indicator
- Layout: colored dot (8x8px rounded-full) + text label
- HIGH: dot + text both #64de8d (secondary/green)
- MED: dot + text both #ffb960 (tertiary/amber)
- LOW: dot + text both muted (on-surface-variant at low opacity)
- Font: label-md IBM Plex Mono 10px uppercase
- Left margin from tag: 16px

### Scrollbar (Custom)
- Width: 4px
- Track: #131313
- Thumb: #2a2a2a
- Thumb hover: #e50914

### Mobile Bottom Nav
- Height: 64px
- Background: surface-container-high
- Border top: 1px outline-variant
- 4 items: Home, Attacks, Analytics, Settings
- Active item: primary-container color + bold

---

## Animations and Interactions
- Hero gradient: follows mouse cursor (mousemove event)
  `radial-gradient(circle at ${x}% ${y}%, rgba(229,9,20,0.12), transparent 70%)`
- Card hover: translateY(-2px), transition 75ms
- Search focus: wrapper scale(1.01)
- Sidebar arrow: rotate 180° on open, CSS transition
- CTA button: active:scale-95, transition 150ms
- Consent button: opacity-50 + grayscale when disabled

---

## Do's and Don'ts

DO:
- Use sharp corners (border-radius: none) everywhere — no rounded cards
- Use IBM Plex Mono for all data, labels, tags, and prompt text
- Keep small-caps + tracking-widest for all section headers
- Show source attribution on every result card
- Maintain high information density — practitioners want data
- Use the 4px red left border as the primary active/selected signal

DON'T:
- Add rounded corners to cards, buttons, or inputs
- Use red (#e50914) for body text or descriptions
- Add gradients, illustrations, or decorative elements
- Use more than two font families (IBM Plex Mono + Inter only)
- Add nav links that don't have real pages behind them
- Use the nav links (Docs, Models, Safety) in Phase 1 — remove them
