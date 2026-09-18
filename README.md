# NFL Player Performance

A data pipeline that pulls NFL stats every day, cleans and models them, and publishes position rankings
(QB, RB, WR, TE, K) to a website. Later phases add weekly predictions that grade themselves, and a mobile app.

**Status: in development.** Phase 1A steps 1-6 are done: ingest, dbt models with data quality tests,
the position rankings, and the published JSON. Nothing is deployed yet, and there is no website yet.

## What works today

One command runs the whole pipeline on your machine and stops at the first failing step:

```bash
nfl-pipeline run            # ingest -> dbt build (models + 116 tests) -> validate -> publish JSON
```

1. **Ingest** downloads [nflverse](https://github.com/nflverse/nflverse-data) Parquet files (schedules, players,
   weekly player stats, play-by-play, injuries, snap counts, rosters, depth charts). It skips files whose source
   has not changed, retries transient failures, checks each file is non-empty Parquet, and writes a manifest.
2. **Transform** (dbt on DuckDB) cleans and models the data: standardized teams and positions, a
   player-week fact table, and the rankings. Every run executes the data quality tests.
3. **Rank** QB, RB, WR, TE, and K two ways: a composite score (70% efficiency, 30% production, each metric
   percentile-scored within the position) and season-to-date fantasy points. Each week is a snapshot, so
   rank movement is available. Players below a minimum role are listed but not ranked.
4. **Publish** validates everything against a schema, then writes versioned JSON to
   `data/published/v1/` (`meta.json` last). If validation fails, nothing is published.

Rankings only use games through the week being ranked, so there is no lookahead.

## Quick start

Local, without Docker:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # on macOS/Linux: .venv/bin/python
.venv/Scripts/nfl-pipeline run
```

Everything lands in `./data/`. Useful options for `run` and `ingest`: `--seasons 2026` or
`--seasons 2021-2025`, `--datasets a,b`, `--force`. You can also run the steps on their own:
`nfl-pipeline ingest`, then `dbt build --project-dir dbt --profiles-dir dbt`, then `nfl-pipeline publish`.

With Docker (no Python needed):

```bash
docker compose run --rm --build pipeline-local run
```

There is also a MinIO service (an S3 stand-in) for trying the ingest against object storage:

```bash
docker compose up -d minio minio-init
docker compose run --rm pipeline ingest --datasets schedules
```

The MinIO console is at http://localhost:9001 (default login `minioadmin` / `minioadmin`, local only).
Stop everything with `docker compose down` (add `-v` to also delete the stored data).
MinIO no longer publishes its community images on Docker Hub, so the compose file pulls a pinned release
from `quay.io`.

## Development

```bash
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format .
```

## Layout

```
pipeline/nfl_pipeline/   ingest, storage, publish, contract (published schema), CLI
pipeline/tests/          tests: unit tests plus dbt integration tests (no network)
dbt/                     staging and mart models, ranking models, seeds, data quality tests
Dockerfile               pipeline image (Python 3.12, non-root, includes the dbt project)
docker-compose.yml       local stack: pipeline-local, plus MinIO for object-storage tests
.github/workflows/       CI: lint, tests, Docker build
```

The ranking method lives in `dbt/seeds/ranking_config.csv` and `ranking_weights.csv`: which metrics count
for each position, their weights, and the minimum role. Change a seed and rebuild to try another setup.

## Data

Data comes from [nflverse](https://github.com/nflverse/nflverse-data), licensed CC BY 4.0. This project is
independent and not affiliated with the NFL or its teams.
