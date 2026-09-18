# NFL Player Performance

Daily NFL stats pipeline that ranks players by position, with a website and (later) weekly predictions.
The full build plan lives outside this repo at `C:\Users\johnw\OneDrive\Documents\nfl player performance\BUILD_PLAN.md`.
Follow its phase order (1A local pipeline, 1B website, 1C AWS, 1D predictions, 1E launch polish, 2 app).

## Commands

- Install: `python -m venv .venv`, then `.venv\Scripts\python -m pip install -e ".[dev]"`
- Tests: `.venv\Scripts\python -m pytest`
- Lint and format: `.venv\Scripts\python -m ruff check .` and `.venv\Scripts\python -m ruff format .`
- Run the ingest locally (writes to `data/`): `.venv\Scripts\nfl-pipeline ingest --datasets schedules`
- Docker stack (MinIO plus the pipeline): `docker compose up -d minio minio-init`, then
  `docker compose run --rm pipeline ingest --datasets schedules`

## Conventions

- Python 3.10+ locally, 3.12 in Docker. Keep code compatible with 3.10.
- Write tests alongside every change. No network in tests: use the fakes in `pipeline/tests/conftest.py`.
- Raw files are immutable dated snapshots; cleaning happens in dbt (phase 1A step 3).
- Only pull data from nflverse's published release files, never from NFL.com. No player headshots.
- Rankings use current-season data only; past seasons feed the backtest and the phase 1D predictions.
