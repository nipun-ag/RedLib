---
name: RedLib Ink & Platinum
description: An institutional adversarial-intelligence workspace for precise, source-grounded AI safety research.
colors:
  vault-black: "oklch(0.08 0 0)"
  platinum-ink: "oklch(0.92 0.012 170)"
  panel-ink: "oklch(0.135 0.012 170)"
  popover-ink: "oklch(0.12 0.01 170)"
  oxidized-teal: "oklch(0.52 0.086 170)"
  white-signal: "oklch(0.99 0 0)"
  secondary-ink: "oklch(0.18 0.014 170)"
  muted-ink: "oklch(0.16 0.01 170)"
  muted-platinum: "oklch(0.72 0.025 170)"
  merlot-caution: "oklch(0.42 0.12 25)"
  destructive-red: "oklch(0.62 0.18 25)"
  platinum: "oklch(0.86 0.01 170)"
  platinum-hairline: "oklch(0.92 0.01 170 / 12%)"
typography:
  display:
    fontFamily: "Newsreader Variable, Newsreader, Times New Roman, serif"
    fontSize: "3rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Newsreader Variable, Newsreader, Times New Roman, serif"
    fontSize: "1.5rem"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Newsreader Variable, Newsreader, Times New Roman, serif"
    fontSize: "1.25rem"
    fontWeight: 400
    lineHeight: 1.25
    letterSpacing: "-0.02em"
  body:
    fontFamily: "IBM Plex Sans Variable, IBM Plex Sans, Segoe UI, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "0.01em"
  label:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1rem
    letterSpacing: "0.12em"
rounded:
  none: "0"
spacing:
  hairline: "1px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  base: "16px"
  lg: "20px"
  xl: "24px"
  2xl: "28px"
  3xl: "32px"
  4xl: "40px"
components:
  button-primary:
    backgroundColor: "{colors.oxidized-teal}"
    textColor: "{colors.white-signal}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    height: "48px"
    padding: "0 32px"
  button-outline:
    backgroundColor: "{colors.vault-black}"
    textColor: "{colors.platinum-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    height: "48px"
    padding: "0 24px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.oxidized-teal}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0"
  panel:
    backgroundColor: "{colors.panel-ink}"
    textColor: "{colors.platinum-ink}"
    rounded: "{rounded.none}"
    padding: "20px"
  search-field:
    backgroundColor: "transparent"
    textColor: "{colors.platinum-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    height: "64px"
    padding: "0 16px"
  technique-chip:
    backgroundColor: "{colors.secondary-ink}"
    textColor: "{colors.muted-platinum}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "4px 10px"
---

# Design System: RedLib Ink & Platinum

## 1. Overview

**Creative North Star: "The Institutional Evidence Vault"**

RedLib is a dark, high-density research instrument for adversarial AI safety
work. Its Ink & Platinum system combines vault-black space, cool metallic text,
oxidized-teal signals, and sharp architectural borders. The interface should
feel authoritative and premium because evidence, provenance, and state are
handled precisely—not because the surface is theatrical.

The research task always outranks atmosphere. Liquid platinum forms create a
quiet sense of controlled technical depth behind the responsible-use gate and
workspace, but they are decorative, non-interactive, and visually subordinate.
Standard controls remain familiar: a fixed technique rail, tabs, search field,
result list, provenance popover, and focused prompt dialog.

This system explicitly rejects generic AI SaaS dashboards, neon cyberpunk
styling, decorative glass everywhere, fake operational metrics, and visual
effects that compete with research tasks. It is also not a restyling of the
legacy obsidian/crimson interface.

**Key Characteristics:**
- Restrained dark product palette with one operational teal signal
- Sharp zero-radius geometry and platinum hairlines
- Editorial serif for brand and findings; technical sans and mono for work
- Provenance-visible, corpus-grounded interactions
- Dense but calm responsive layouts
- Motion that explains state, quantity, or attention

**System boundary.** React 19, Vite, TypeScript, Tailwind CSS v4, shadcn/ui
primitives, Radix behavior, Lucide icons, and Motion implement the system under
`frontend/`. Routes are `/` for responsible access and `/workspace` for the
research surface; `/index.html` and `/search.html` are compatibility redirects.
Unknown routes redirect to `/`. The product is dark-only: `html` uses
`color-scheme: dark` with duplicated `.dark` tokens and no theme switcher.
Global `border-radius: 0 !important` overrides rounded styles from generated
shadcn primitives. Scaffolded but unused primitives such as Chart/Recharts and
Card must not be treated as part of the visual system.

**Responsive structure.** Below the medium breakpoint, the technique rail
stacks above the workspace with a minimum height of 280px. At 768px it becomes
a 280px fixed rail beside a flexible content column; at 1280px the rail grows
to 300px. Statistic panels progress from one to two to three columns, and the
search action stacks below its field on narrow screens.

## 2. Colors

The palette is cool, restrained, and state-driven. OKLCH values in the
frontmatter are normative and mirror `frontend/src/index.css`.

### Primary
- **Oxidized Teal:** Reserved for primary actions, active filters, focus,
  selected states, links under interaction, count bars, and grounded-result
  signals. It is never a decorative wash across the whole interface.
- **White Signal:** High-contrast copy placed on the teal primary action.

### Secondary
- **Secondary Ink:** Distinguishes selected tabs, secondary control surfaces,
  and contextual panels without adding another accent hue.
- **Muted Ink:** Skeletons, subdued states, and quiet surface separation.

### Tertiary
- **Merlot Caution:** A sparse caution token. It supports responsible-use and
  risk semantics, not decoration.
- **Destructive Red:** Request failures and destructive or invalid states only.

### Neutral
- **Vault Black:** The global canvas and deepest spatial layer.
- **Panel Ink:** Standard panel, result, sidebar, header, and stat surfaces.
- **Popover Ink:** Elevated transient surfaces such as source provenance and
  prompt detail.
- **Platinum Ink:** Primary readable text.
- **Muted Platinum:** Supporting descriptions, source names, status copy, and
  secondary metadata.
- **Platinum:** High-value neutral indicators and medium-confidence signals.
- **Platinum Hairline:** The 1px structure used instead of shadows or rounded
  cards.

**The One Signal Rule.** Oxidized teal marks action, selection, focus, or
meaningful data. If it does none of those jobs, remove it.

**The Merlot Restraint Rule.** Merlot and destructive red communicate caution
or failure only. They never become a second brand accent.

**The Contrast Rule.** Body and placeholder text target WCAG 2.2 AA. Do not
lower supporting copy beneath the committed muted-platinum token simply to
make the interface feel quieter.

## 3. Typography

**Display Font:** Newsreader Variable, with Newsreader and Times New Roman
fallbacks.

**Body Font:** IBM Plex Sans Variable, with IBM Plex Sans and Segoe UI
fallbacks.

**Label/Mono Font:** IBM Plex Mono, with `ui-monospace` fallback

**Character:** Newsreader gives the brand, corpus counts, summaries, and prompt
detail an editorial research character. IBM Plex Sans keeps controls and prose
familiar; IBM Plex Mono distinguishes identifiers, counts, taxonomy metadata,
and raw prompt text.

### Hierarchy
- **Display** (400, 2.25–3rem, 1.0): The gate wordmark and live corpus count.
- **Headline** (400, 1.5rem, 1.2): Workspace identity, stat values, and prompt
  dialog title.
- **Title** (400, 1.25rem, 1.25): AI summary and section-level findings.
- **Body** (400, 0.875–1rem, 1.55): Interface copy, explanations, excerpts, and
  source labels. Narrative prose is capped with `max-w-prose`.
- **Raw Prompt** (400, 0.8125rem, 1.5rem): Full prompt text in IBM Plex Mono,
  preserving whitespace and wrapping long lines.
- **Label** (400–500, 0.75rem, 0.12em, uppercase): Metadata, tabs, actions,
  category chips, and section identifiers.
- **Micro Metadata** (400, 0.625–0.6875rem): Dataset hosts, dataset IDs, and
  compact confidence/category labels.

Headings use balanced wrapping and `-0.02em` tracking. Body copy inherits
`0.01em` tracking. Numeric values use tabular figures.

**The Editorial Boundary Rule.** Newsreader belongs to brand, findings, and
important values. Never use it for buttons, input text, tabs, filter rows, or
technical metadata.

**The Mono Meaning Rule.** Monospace communicates data, identifiers, labels,
counts, or raw corpus content. It is not a decorative body font.

## 4. Elevation

RedLib is flat by default. Depth comes from tonal layers, 1px hairlines,
overlays, and state changes—not ambient card shadows. Panels remain flush and
architectural at rest. The source popover removes the library default shadow;
the prompt dialog uses an 80% black overlay with a restrained backdrop blur.

### State Vocabulary
- **Rest:** Panel ink against vault black with a platinum hairline.
- **Hover:** A subtle border shift toward teal and, on result/stat surfaces,
  a maximum 2px upward translation over 300ms.
- **Focus:** A 2px oxidized-teal outline with 2px offset globally; Radix and
  shadcn controls may add their three-pixel translucent focus ring.
- **Selected:** Teal-tinted fill plus a one-pixel teal outline.
- **Modal:** Popover ink above an 80% black overlay; content is centered and
  constrained to 980px and the viewport height.

**The Flat Evidence Rule.** Shadows do not make ordinary content important.
Hierarchy must come from placement, typography, borders, and semantic color.

**The Hairline Rule.** Structural borders remain 1px. Thick colored side
stripes are prohibited; the single-pixel AI Summary signal is the maximum.

## 5. Components

All interactive components use Radix/shadcn behavior and Lucide icons. Global
zero-radius enforcement overrides rounded library defaults. Controls require
default, hover, focus-visible, active, disabled, loading, and error treatment
where the state applies.

### Responsible Use Gate
- A centered panel (`max-width: 36rem`) sits over the stronger gate variant of
  the liquid atmosphere.
- A live animated corpus count falls back to 168,115 records if stats fail.
  Gate stats failure is silent; the workspace stats bar instead renders `—`.
- Three numbered research conditions make responsible use part of entry.
- The acknowledgment checkbox starts unchecked on each unacknowledged visit and
  enables the full-width 48px primary action only when checked.
- Acceptance persists under
  `redlib.researchGateAcknowledged` in `localStorage`; previously acknowledged
  users are redirected to `/workspace` with history replacement. Direct
  workspace access without acknowledgment redirects to `/`.

### Workspace Shell and Navigation
- Mobile uses a stacked rail and content flow; desktop uses the fixed-width
  technique rail beside a flexible workspace.
- The 64px minimum header carries the RedLib identity and external GitHub link.
  The wordmark is identity, not a back-navigation affordance.
- Search and Browse use a bordered 44px tab list with mono labels and a
  secondary-ink active fill.
- Selecting a technique always switches to Browse, clears search state, resets
  pagination, and fetches the first 20 records. Clearing the filter resets both
  browse and search state. An active category may remain as a search filter
  after browsing until the filter is cleared.
- Selecting Browse without a category triggers a 1.8s sidebar attention window;
  motion users see two 550ms outline pulses. Reduced-motion users receive no
  pulse.
- The main content column scrolls independently on desktop while the rail
  remains fully usable.

### Technique Rail
- The header reports the number of known families and total records.
- Each canonical category is a full-width 48px-minimum filter row with a
  proportional teal background bar, a concise display label, and a tabular
  count.
- Bars are normalized against the largest category and have a 4% visual floor
  so small but nonzero categories remain visible.
- Active rows use teal tint and a one-pixel outline. Hover changes surface and
  text without introducing a second color.
- Selecting Browse without a category pulses the filter rows twice with a
  restrained 550ms outline signal. Reduced-motion users receive no pulse.
- Loading uses inline skeletons rather than replacing navigation structure.

### Technique Display Labels
`frontend/src/lib/taxonomy.ts` owns display aliases through `CATEGORY_LABELS`
and `categoryLabel()`.

- `Role-Based Task Framing` → `Role Play`
- `Fictional / Hypothetical Framing` → `Fictional Framing`
- `Authority or Legitimacy Spoofing` → `Privilege Escalation`
- `Obfuscation / Encoding` → `Obfuscation`
- `Simulation or Sandbox Framing` → `Virtualization`
- `Dual-Response or Comparative Framing` → `Dual Response`
- `Legitimate Context or Research Framing` → `Benign Framing`
- `Contextual Reframing or Euphemism` → `Disguised Intent`

Aliases are render-time text only. Canonical names remain in component state,
selection callbacks, API requests, API responses, Qdrant metadata, and corpus
artifacts. Never derive a canonical name from a display alias. Unmapped
categories render their canonical name as a safe fallback; title text retains
the canonical value where compact labels appear.

### Corpus Statistics and Source Provenance
- Total Prompts, Sources, and Last Sync use responsive panel columns and
  skeleton placeholders while `/api/stats` loads.
- Statistic values use Newsreader and tabular figures.
- Sources is a click/focus button, not a hover-only card. It opens a portal-based
  provenance popover aligned below the trigger.
- The popover is limited to `min(100vw - 2rem, 22rem)` wide and 60vh/22rem high,
  with an internal scroll area. It lists exactly seven frontend-owned datasets
  from `CORPUS_SOURCES`, each with readable name, dataset ID, Hugging Face host,
  and an external link that opens in a new tab.
- The API `total_sources` count and the seven-item provenance list are separate
  data sources; keep the frontend registry aligned with
  `corpus/fetch_corpus.py` SOURCE_REGISTRY.
- Source links expose hover and keyboard focus states and use the external-link
  icon consistently.

### Search Field and Actions
- The search control is a 64px bordered panel containing a leading Search icon
  and borderless input. `focus-within` shifts the panel border toward teal.
- The primary Search button matches the field height on larger screens and
  stacks below it on narrow screens.
- Empty queries disable Search. Enter submits from the field. Loading changes
  the action label to `Searching…`.
- Primary buttons use oxidized teal; outline buttons serve pagination and
  secondary actions; ghost buttons serve inline actions.

### Summary, Technique Chips, and Result Cards
- Search returns one AI Summary panel followed by grounded result cards.
- Summary prose stays within readable measure. Technique breakdown uses compact
  mono chips showing display label and count; canonical names remain available
  through title text.
- Result cards show a technique badge, source, excerpt, and explicit
  `View Full Prompt` action. Confidence appears on search cards only; browse
  cards omit it.
- Confidence is redundant by design: text plus a small square signal. High is
  teal, medium is platinum, and low is muted.
- Result cards contain excerpts only. They never expose the full prompt before
  explicit inspection.

### Browse Mode
- Browse requires a selected technique and explains the active category before
  listing raw corpus records.
- The category description uses a subtle secondary surface and teal-aware
  border.
- Results load in pages of 20. A 48px outline `Load more` action appears only
  when a cursor remains and changes to `Loading…` while appending.

### Prompt Detail Dialog
- The dialog lazily requests `/api/prompts/{id}` only after explicit user
  action.
- It uses a maximum width of 980px, viewport-constrained height, fixed header
  and footer, and a scrollable body.
- Header metadata includes prompt ID and the display alias while preserving the
  canonical category in title text. The body renders raw text in IBM Plex Mono.
- Loading uses a full-width skeleton; errors remain in-dialog; source
  attribution stays visible in the footer.
- Radix supplies keyboard focus management and Escape behavior. A visible,
  labeled close button remains in the header.

### Loading, Empty, and Error States
- Skeletons preserve the approximate geometry of stats, filters, summaries,
  and result cards.
- Empty search and browse states describe what happened in one sentence.
- Errors use destructive text on a standard panel and remain inside the
  affected workflow.
- Search and browse result regions use `aria-live="polite"` so asynchronous
  changes are announced without interrupting the researcher.

### Motion and Atmosphere
- Standard hover and state transitions run for 150–300ms with exponential or
  quartic ease-out curves.
- Animated counts use a 900ms cubic ease-out and tabular figures.
- Liquid SVG paths drift for 18–22 seconds using transform and opacity only.
  The gate receives the stronger composition; workspace forms remain at
  35–40% opacity.
- The atmosphere is `aria-hidden`, pointer-inert, and never carries meaning.
- `prefers-reduced-motion` collapses animation and transition durations to
  0.01ms; Motion hooks also bypass count animation and attention pulses.
- Do not add orchestrated page-load choreography.

### Accessibility
- Target WCAG 2.2 AA for contrast, keyboard operation, focus visibility, and
  semantic structure. Treat this as a testing target, not demonstrated
  compliance.
- Every icon-only button has an accessible label; decorative icons and
  atmosphere are hidden from assistive technology.
- The search field uses a visually hidden `<label>` (`Search the classified
  corpus`) so it has a dedicated accessible name beyond the placeholder.
- Popovers and dialogs render through portals to avoid clipping.
- Focus-visible styling must remain distinct from hover and selected states.
- Interactive targets use a minimum 44px height where practical: Clear filter,
  View Full Prompt, and the prompt-modal close control are at least `h-11`;
  primary search and pagination actions remain 48–64px.

## 6. Do's and Don'ts

### Do:
- **Do** preserve the Ink & Platinum palette and use oxidized teal only for
  action, selection, focus, and meaningful data.
- **Do** use sharp zero-radius geometry and 1px platinum hairlines throughout.
- **Do** keep provenance visible through source labels, dataset IDs, counts,
  confidence, and direct dataset links.
- **Do** preserve canonical taxonomy names as data and API identifiers while
  resolving short labels only through `categoryLabel()`.
- **Do** keep result excerpts separate from full-prompt inspection.
- **Do** use skeletons for loading, concise inline empty states, and contextual
  error panels.
- **Do** preserve keyboard behavior, visible focus, polite announcements, and
  reduced-motion alternatives.
- **Do** validate layouts at stacked mobile, 768px two-column, and 1280px
  expanded-rail breakpoints.

### Don't:
- **Don't** create a generic AI SaaS dashboard or add fake operational metrics.
- **Don't** use neon cyberpunk styling, decorative glass everywhere, or visual
  effects that compete with research tasks.
- **Don't** revive the legacy obsidian/crimson identity.
- **Don't** add charts when the filter rows and counts communicate the same
  information more directly. The current proportional bars are navigation,
  not decorative analytics.
- **Don't** use gradients in text, thick colored side stripes, rounded cards,
  or ambient card shadows.
- **Don't** use Newsreader in controls or IBM Plex Mono as decorative prose.
- **Don't** send a display alias to the API, persist it as taxonomy data, or
  reverse-map it into a canonical category.
- **Don't** introduce decorative motion, bounce/elastic easing, or content that
  remains hidden until an animation completes.
- **Don't** invent custom interaction patterns where familiar tabs, buttons,
  fields, popovers, and dialogs already solve the task.
