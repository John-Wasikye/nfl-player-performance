# NFL Player Performance

Daily NFL stats pipeline that ranks players by position, with a website and (later) weekly predictions.
The full build plan lives outside this repo at `C:\Users\johnw\OneDrive\Documents\nfl player performance\BUILD_PLAN.md`.
Follow its phase order (1A local pipeline, 1B website, 1C AWS, 1D predictions, 1E launch polish, 2 app).
**At the start of a session, read `C:\Users\johnw\OneDrive\Documents\nfl player performance\SESSION_CONTEXT.md`**:
current status, decisions, open questions, and practical gotchas. Keep it up to date as work progresses.

## Commands

- Install: `python -m venv .venv`, then `.venv\Scripts\python -m pip install -e ".[dev]"`
- Tests: `.venv\Scripts\python -m pytest`
- Lint and format: `.venv\Scripts\python -m ruff check .` and `.venv\Scripts\python -m ruff format .`
- Whole pipeline locally (ingest, dbt build with tests, publish): `.venv\Scripts\nfl-pipeline run`
- Backtest (needs a built warehouse; writes docs/backtest.md): `.venv\Scripts
fl-pipeline backtest`
- Just the ingest: `.venv\Scripts\nfl-pipeline ingest --datasets schedules`
- dbt (from the repo root, with `.venv\Scripts` on PATH): `dbt build --project-dir dbt --profiles-dir dbt`.
  After changing a seed's columns, run `dbt seed --full-refresh` or the old columns stay.
- Docker stack (MinIO plus the pipeline): `docker compose up -d minio minio-init`, then
  `docker compose run --rm pipeline ingest --datasets schedules`

- Website (from `web/`): `npm run dev` (syncs published data first), `npm run lint`, `npm run typecheck`,
  `npm test`, `npm run test:e2e`. Read `web/AGENTS.md`: this Next.js version differs from older ones, so check
  `web/node_modules/next/dist/docs/` before changing framework-level code.

## Conventions

- Python 3.10+ locally, 3.12 in Docker. Keep code compatible with 3.10.
- Write tests alongside every change. No network in tests: use the fakes in `pipeline/tests/conftest.py`.
- Raw files are immutable dated snapshots; cleaning happens in dbt. dbt reads the newest snapshot only.
- nflverse's weekly stats file is `stats_player_week_<season>` (the `regpost` file is season totals, no week).
- Ranking rules: minimum role scales with games the team has played; kickers get standard fantasy scoring
  because nflverse does not score them; rankings are "as of week N" with no lookahead (there is a test).
- The published JSON is a contract (`contract.py`); changing it means bumping `SCHEMA_VERSION`.
- Only pull data from nflverse's published release files, never from NFL.com. No player headshots.
- Rankings use current-season data only; past seasons feed the backtest and the phase 1D predictions.
- Website: static export, data fetched in the browser from `/data/v1`. Avatars are initials on team colors
  (no photos or logos). Keep `web/lib/types.ts` in step with `pipeline/nfl_pipeline/contract.py`.
- Website tests must not depend on live data: e2e uses `web/e2e/fixtures`.
