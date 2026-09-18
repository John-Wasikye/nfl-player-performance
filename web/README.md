# Website

The public site for NFL Player Performance: position rankings (composite score and fantasy points),
player pages with rank history and a score breakdown, and a methodology page that shows the backtest.

It is a fully static Next.js site. Every page is pre-built HTML, and the rankings are fetched in the
browser from the pipeline's published JSON (`/data/v1/...`), so the daily data refresh never needs a
site rebuild.

## Run it

You need the published data first. From the repo root, run the pipeline once (`nfl-pipeline run`), then:

```bash
cd web
npm install
npm run dev          # copies ../data/published/v1 into public/data, then starts http://localhost:3000
```

| Command | What it does |
|---|---|
| `npm run dev` | Sync the data and start the dev server |
| `npm run build` | Build the static site into `out/` |
| `npm run serve` | Serve `out/` locally (`node scripts/serve-static.mjs out`) |
| `npm run lint` / `npm run typecheck` | ESLint / TypeScript |
| `npm test` | Unit tests (Vitest) |
| `npm run test:e2e` | End-to-end and accessibility tests (Playwright, against fixture data) |

Set `NEXT_PUBLIC_DATA_BASE` to read the data from somewhere else, for example a CloudFront address.

## Pages

| Route | What it shows |
|---|---|
| `/` | Season and week status, biggest movers, the top five at each position |
| `/rankings/[position]/` | Sortable, filterable table for QB, RB, WR, TE, or K; composite or fantasy view; week selector |
| `/player/?id=...` | Rank history chart, stat tiles, and why the player is ranked where they are |
| `/methodology/` | The exact settings in use and the backtest results |
| `/about/` | Data sources, attribution, glossary, disclaimers |

A single static `/player/` page serves every player (the id is a query parameter), so the site does not
need to know which players exist when it is built. View, week, and player are in the URL, so links can
be shared.

## How it is built

- **Next.js (static export), TypeScript, Tailwind CSS.** No UI or chart library: the small set of
  components and the SVG charts are hand-written, which keeps the JavaScript small.
- **Light and dark themes** from CSS variables. A saved choice is applied before first paint; otherwise
  the system setting is followed.
- **Accessible by design:** semantic tables with sort state, real links for navigation, a skip link,
  focus styles, chart text alternatives, and movement shown with arrows and words, never color alone.
- **No photos or logos.** Players get an initials avatar on their team's color.
- **Fails visibly:** loading skeletons, an error state with retry, an empty state for no matches, and a
  banner if the published data is more than 36 hours old.
- **Data contract:** `lib/types.ts` mirrors `pipeline/nfl_pipeline/contract.py`. The site refuses data
  whose `schema_version` it does not understand.

## Tests

- **Unit tests** (`tests/`): formatting, sorting and filtering, team colors and their contrast, chart
  helpers, and the data loader (including a regression test for a shared-request bug).
- **End-to-end tests** (`e2e/`): every page and interaction, run against a small fixed copy of the data in
  `e2e/fixtures` (refresh it with `node scripts/make-fixtures.mjs`).
- **Accessibility** (`e2e/a11y.spec.ts`): axe checks for WCAG 2.2 A/AA on every page in both themes, plus
  a keyboard-only journey. These do not replace testing with a screen reader.
- **Phone layout** (`e2e/mobile.spec.ts`): no sideways scrolling, controls reachable, touch targets large enough.

This project uses a recent Next.js whose APIs can differ from older versions; see `AGENTS.md` and the
docs in `node_modules/next/dist/docs/` before changing framework-level code.
