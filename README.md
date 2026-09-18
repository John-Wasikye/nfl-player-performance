# NFL Player Performance

A data pipeline that pulls NFL stats every day, cleans and models them, and publishes position rankings
(QB, RB, WR, TE, K) to a website. Later phases add weekly predictions that grade themselves, and a mobile app.

**Status: in development.** Phase 1A, step 2 is done: the project skeleton and the ingest of raw
[nflverse](https://github.com/nflverse/nflverse-data) files. Nothing is deployed yet.

## What works today

`nfl-pipeline ingest` downloads nflverse Parquet files (schedules, players, player stats, play-by-play,
injuries, snap counts, rosters, depth charts) into a raw storage layer. It:

- skips files whose source has not changed since the last run (using nflverse's `timestamp.json`),
- retries transient failures with backoff and reports them without stopping the other files,
- validates that each download is a non-empty Parquet file before storing it,
- stores files untouched under `raw/<dataset>/season=<year>/ingest_date=<date>/`, and
- writes a manifest for every run under `manifests/runs/`.

Storage is the local filesystem by default, or S3-compatible storage (MinIO in Docker, S3 on AWS later).

## Quick start

Local, without Docker:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # on macOS/Linux: .venv/bin/python
.venv/Scripts/nfl-pipeline ingest --datasets schedules
```

Files land in `./data/`. Useful options: `--seasons 2026` or `--seasons 2021-2025`, `--datasets a,b`, `--force`.

With Docker (MinIO stands in for S3, no AWS needed):

```bash
docker compose up -d minio minio-init
docker compose run --rm --build pipeline ingest --datasets schedules
```

The MinIO console is at http://localhost:9001 (default login `minioadmin` / `minioadmin`, local only).
Stop everything with `docker compose down` (add `-v` to also delete the stored data).

MinIO no longer publishes its community images on Docker Hub, so the compose file pulls a pinned release from `quay.io`.

## Development

```bash
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format .
```

## Layout

```
pipeline/nfl_pipeline/   ingest, storage, and CLI code
pipeline/tests/          unit tests (no network; fakes in conftest.py)
Dockerfile               pipeline image (Python 3.12, non-root)
docker-compose.yml       local stack: MinIO + pipeline
.github/workflows/       CI: lint, tests, Docker build
```

## Data

Data comes from [nflverse](https://github.com/nflverse/nflverse-data), licensed CC BY 4.0. This project is
independent and not affiliated with the NFL or its teams.
