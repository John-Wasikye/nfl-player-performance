# NFL Player Performance

A data pipeline that pulls NFL stats every day, ranks players by position, and projects the coming week.
Everything is published to a website: **https://nflstats.johnwasikye.com**

I built it to see how far a small, carefully tested pipeline can go, from raw public data to a deployed,
monitored product. It runs by itself on AWS, and I priced it at about a dollar a month.

## What it does

- **Rankings.** QB, RB, WR, TE and K, ranked two ways: a composite score and season-to-date fantasy points.
  Every week is a snapshot, so you can see who moved. Rankings only use games played through the week being
  ranked, and a test enforces that.
- **Projections.** A forecast for each player in the coming week, with the range it could land in. Players
  ruled out are dropped, and a questionable player shows both his score if he plays and the chance he does.
- **A report card.** Projections are locked before the first kickoff and never changed, then graded against
  what happened. The page shows the results, including weeks where the model lost to a plain average.
  Until a locked week finishes, it says there is nothing to grade yet.
- **An experiment log.** Every change I try against the model is recorded with its result, including the ones
  that failed. A change ships only if it beats the current model on weeks neither was trained on.

## How it works

The data flows in one direction: public nflverse files, then ingest into a raw lake in S3, then dbt on DuckDB,
then rankings and projections, then a validation gate, then JSON in S3, then CloudFront, then the site.

1. **Ingest** downloads 16 [nflverse](https://github.com/nflverse/nflverse-data) datasets as Parquet: schedules,
   players, weekly stats, play-by-play, injuries, snap counts, rosters, depth charts, participation, advanced
   stats, charting data and Next Gen Stats. It skips files whose source has not changed, retries transient
   failures, and checks that each file is non-empty Parquet.
2. **Transform** is dbt on DuckDB: cleaned staging models, a player-week fact table, the ranking models and a
   point-in-time feature store for the predictions. Every run executes the data tests (158 checks, including
   tests that prove a feature never sees its own week).
3. **Rank and project.** The composite score mixes efficiency and production metrics, each percentile-scored
   within the position, weighted 20% efficiency and 80% production, the split that held up best in the
   backtest. The weights live in `dbt/seeds/ranking_config.csv`. Projections come from a ridge and
   LightGBM ensemble with conformal ranges, evaluated walk-forward so no season is scored on data it saw.
4. **Validate and publish.** The published JSON is a versioned contract. A validation gate checks the schema,
   the row counts and freshness, and writes nothing if anything is wrong, so a bad run leaves the old data live.
   `meta.json` is written last.

A backtest in [docs/backtest.md](docs/backtest.md) checks whether rank at week N predicts week N+1. Ranking
with a heavy efficiency weight predicts noticeably worse than ranking by fantasy points per game, and a mostly
production-based composite roughly ties that simple baseline. The projection method and its limits are written
up in [docs/prediction-research.md](docs/prediction-research.md).

## Running on AWS

The task runs on Fargate once a day, started by EventBridge. Terraform builds everything.

| Piece | What it does |
|---|---|
| **S3** | Four buckets: raw data, locked records (Object Lock, governance mode), the site, and Terraform state. All private. |
| **Fargate** | Runs `nfl-pipeline daily` from the image in ECR: the full run, then the week's projections. |
| **CloudFront** | The only reader of the site bucket. HTTPS, security headers and short caching for the daily data. |
| **CloudWatch and SNS** | Alarms email me on a failed run, a missed run, or a task that never started. |
| **GitHub Actions** | Tests every change and deploys on merge. It signs in to AWS with OIDC, so there is no stored key. |

Three decisions shape the rest:

- **Derived state is disposable, records are not.** The warehouse is rebuilt from raw data on every run and
  never read back. Locked forecasts and the experiment ledger are the only records, and they are write-once.
  See [docs/storage-design.md](docs/storage-design.md).
- **Nothing fails quietly.** Alarms treat missing data as a failure, and each alert path was fired once on
  purpose to see the email arrive. The full list is in [docs/no-silent-failures.md](docs/no-silent-failures.md).
- **A forecast cannot be locked late.** The daily run locks a week only inside the 24 hours before its first
  kickoff. If kickoff has passed and the week is unlocked, it refuses, writes nothing and emails me.

## Run it yourself

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # macOS and Linux: .venv/bin/python
.venv/Scripts/nfl-pipeline run
```

Everything lands in `./data/`. Useful commands:

| Command | What it does |
|---|---|
| `nfl-pipeline run` | Ingest, dbt build with tests, validate, publish. Stops at the first failing step. |
| `nfl-pipeline daily` | `run`, then project the coming week and lock it if its window has opened. This is what AWS runs. |
| `nfl-pipeline predict` | Project the coming week, grade finished ones, publish both. Add `--lock` only before the first kickoff. |
| `nfl-pipeline experiment` | Write the failure report, or run one candidate through the promotion gate with `--run NAME`. |
| `nfl-pipeline backtest` | Score the rankings against the following week. |
| `nfl-pipeline ingest` and `publish` | Run those two steps alone. |

Options for `run` and `ingest`: `--seasons 2026` or `--seasons 2021-2025`, `--datasets a,b`, `--force`.

With Docker, no Python needed:

```bash
docker compose run --rm --build pipeline-local run
```

There is also a MinIO service, an S3 stand-in, for trying the pipeline against object storage:

```bash
docker compose up -d minio minio-init
docker compose run --rm pipeline ingest --datasets schedules
```

The MinIO console is at http://localhost:9001 (login `minioadmin` / `minioadmin`, local only). MinIO no longer
publishes community images on Docker Hub, so the compose file pulls a pinned release from `quay.io`.

The website has its own instructions in [web/README.md](web/README.md), and the infrastructure in
[infra/README.md](infra/README.md).

## Tests

```bash
.venv/Scripts/python -m pytest                      # 268 tests
.venv/Scripts/python -m ruff check .
cd web && npm test && npm run test:e2e              # 59 unit and 91 end-to-end, including accessibility
```

CI runs all of it on every change, plus `terraform fmt` and `validate`, and fails on any high-severity
advisory in what the site ships. `main` is protected, so changes arrive through a pull request.

## Layout

```
pipeline/nfl_pipeline/   ingest, storage, publish, contract (the published schema), predictions, CLI
pipeline/tests/          unit tests and dbt integration tests (no network)
dbt/                     staging, marts, ranking and feature models, seeds, data tests
web/                     the website (Next.js static export): pages, components, tests
infra/                   Terraform: buckets, ECR, ECS, schedule, alarms, CloudFront, domain, GitHub OIDC
research/                the studies behind the prediction design, with results
docs/                    design notes, the backtest, the research paper, held-back dependencies
.github/workflows/       CI, Terraform plan on pull requests, deploy on merge
```

## What is not done

- A mobile app is planned and not started.
- No week has been graded yet. The first graded week will appear on the report card once a locked week ends.

## Data

Data comes from [nflverse](https://github.com/nflverse/nflverse-data), licensed CC BY 4.0. This project is
independent and not affiliated with the NFL or its teams. It uses no NFL.com data and no player photos or logos.
