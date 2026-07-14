# RedLib - Design System

## Current Frontend Baseline
- Frontend runtime: Vite + React
- Styling pipeline: Tailwind via `src/index.css` with PostCSS
- Current shell: a minimal full-screen landing state that renders
  `RedLib` centered on the page

## Color Tokens
Tailwind color tokens currently defined in `frontend/tailwind.config.js`:
- `background`: `#131313`
- `surface-low`: `#1c1b1b`
- `surface`: `#201f1f`
- `surface-high`: `#2a2a2a`
- `surface-highest`: `#353534`
- `primary`: `#e50914`
- `primary-dark`: `#c0000c`
- `on-primary`: `#fff7f6`
- `on-surface`: `#e5e2e1`
- `on-surface-variant`: `#e9bcb6`
- `outline-variant`: `#5e3f3b`
- `outline`: `#af8782`
- `secondary`: `#64de8d`
- `tertiary`: `#ffb960`

## Utilities
- `frontend/src/lib/utils.js` exposes `cn(...inputs)` using `clsx` and
  `tailwind-merge`
- `frontend/src/config.js` exposes `API_BASE_URL` from Vite env config

## Environment
- Local frontend API target: `frontend/.env.local`
- Production frontend API target: `frontend/.env.production`
