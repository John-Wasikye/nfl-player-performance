# NFL Player Performance

Daily NFL stats pipeline that ranks players by position, with a website, weekly predictions that grade
themselves, and a deployment on AWS. The site is live at https://nflstats.johnwasikye.com.
The full build plan lives outside this repo at `C:\Users\johnw\OneDrive\Documents\nfl player performance\BUILD_PLAN.md`.
Follow its phase order (1A local pipeline, 1B website, 1C weekly predictions, 1D AWS, 1E launch polish, 2 app).
**At the start of a session, read `C:\Users\johnw\OneDrive\Documents\nfl player performance\SESSION_CONTEXT.md`**:
current status, decisions, open questions, and practical gotchas. Keep it up to date as work progresses.

## Commands

- Install: `python -m venv .venv`, then `.venv\Scripts\python -m pip install -e ".[dev]"`
- Tests: `.venv\Scripts\python -m pytest`
- Lint and format: `.venv\Scripts\python -m ruff check .` and `.venv\Scripts\python -m ruff format .`
- Whole pipeline locally (ingest, dbt build with tests, publish): `.venv\Scripts\nfl-pipeline run`
- Backtest (needs a built warehouse; writes docs/backtest.md): `.venv\Scripts\nfl-pipeline backtest`
- Weekly projections (predict, grade, publish): `.venv\Scripts\nfl-pipeline predict`.
  Add `--lock` ONLY before the week's first kickoff: a locked week cannot be rewritten, and that is
  what makes the Report card honest. `--lock-when-due` is the unattended form: it locks only inside the
  24 hours before the first kickoff, publishes an existing lock instead of recomputing it, and refuses
  (exit 1, writes nothing) once kickoff has passed with the week unlocked.
- What AWS runs each day: `nfl-pipeline daily`, which is `run` followed by `predict --lock-when-due`.
- The learning loop: `.venv\Scripts\nfl-pipeline experiment` writes `docs/last-week.md` (where the
  model missed, and which datasets are still unused). Read it, add one candidate to
  `pipeline/nfl_pipeline/predict/proposals.py`, then `nfl-pipeline experiment --run <name>`.
  The promotion gate decides and the verdict is appended to the ledger either way. Do not delete a
  rejected candidate: the code is the record of what was tried.
- Just the ingest: `.venv\Scripts\nfl-pipeline ingest --datasets schedules`
- dbt (from the repo root, with `.venv\Scripts` on PATH): `dbt build --project-dir dbt --profiles-dir dbt`.
  After changing a seed's columns, run `dbt seed --full-refresh` or the old columns stay.
- Infrastructure (Terraform, from `infra/`): run `aws sso login --profile nfl_player_stats`, set
  `$env:AWS_PROFILE = "nfl_player_stats"`, then `terraform plan`. Terraform is applied by hand and CI only
  plans. The code names no AWS profile, so CI and the laptop run the same files. Details: `infra/README.md`.
- Changes reach `main` by pull request only (branch protection; `test`, `web` and `infra` must pass). Merging
  deploys: the image goes to ECR as `:latest` and the commit SHA, and the site goes to S3 and CloudFront.
- Docker stack (MinIO plus the pipeline): `docker compose up -d minio minio-init`, then
  `docker compose run --rm pipeline ingest --datasets schedules`

- Website (from `web/`): `npm run dev` (syncs published data and rebuilds the research page first),
  `npm run lint`, `npm run typecheck`, `npm test`, `npm run test:e2e`.
  The e2e suite builds into `out-e2e/` via `NEXT_DIST_DIR`, so it can run with a dev server up;
  they used to share `.next` and corrupt each other. `npm run research` alone regenerates the
  research page after editing `docs/prediction-research.md`. Read `web/AGENTS.md`: this Next.js version differs from older ones, so check
  `web/node_modules/next/dist/docs/` before changing framework-level code.

## Conventions

- Python 3.10+ locally, 3.12 in Docker. Keep code compatible with 3.10.
- Write tests alongside every change. No network in tests: use the fakes in `pipeline/tests/conftest.py`.
- Raw files are immutable dated snapshots; cleaning happens in dbt. dbt reads the newest snapshot only.
- **Storage layout is decided: read `docs/storage-design.md` before moving any file or changing
  `config.py`/`storage.py`/`profiles.yml`.** In short: the warehouse is derived, so it is rebuilt from
  raw every run and never read back, but the finished copy is published to S3 as a read-only snapshot
  so `backtest` and `experiment` can run as on-demand AWS tasks without rebuilding. dbt reads raw
  straight from S3 via `RAW_ROOT`. Locked predictions and the ledger are records, kept write-once with
  S3 conditional writes plus Object Lock (governance mode), and mirrored into git by a scheduled action.
  Only the weekly Claude analyst session stays on the laptop, to keep it inside the Pro plan.
- nflverse's weekly stats file is `stats_player_week_<season>` (the `regpost` file is season totals, no week).
- Ranking rules: minimum role scales with games the team has played; kickers get standard fantasy scoring
  because nflverse does not score them; rankings are "as of week N" with no lookahead (there is a test).
- The published JSON is a contract (`contract.py`); changing it means bumping `SCHEMA_VERSION`.
- Only pull data from nflverse's published release files, never from NFL.com. No player headshots.
- Rankings use current-season data only; past seasons feed the backtest and the phase 1D predictions.
- Website: static export, data fetched in the browser from `/data/v1`. Avatars are initials on team colors
  (no photos or logos). Keep `web/lib/types.ts` in step with `pipeline/nfl_pipeline/contract.py`.
- Website tests must not depend on live data: e2e uses `web/e2e/fixtures`.
- Voice for anything public (site copy, docs, README, ledger wording): first person singular, plain words, no
  "we" or "our", no em dashes or spaced hyphens used as dashes, and no filler such as "honest", "genuinely",
  "actually" or "simply". The reader is a data engineer or a recruiter. Do not add narrating code comments.
- Held-back dependencies and the reasons are in `docs/dependencies.md`. Check it before bumping TypeScript,
  `@types/node` or ESLint.

<!-- BEGIN AWS Agent Toolkit rules -->
**Project override:** infrastructure for this project is written in **Terraform** (`infra/`), not CDK or
CloudFormation. AWS CLI profile: `nfl_player_stats` (IAM Identity Center, run `aws sso login --profile nfl_player_stats`).

# AWS Guidance

- Where these AWS rules conflict with the project's own instructions, the
  project's instructions take precedence.
- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.

## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.
<!-- END AWS Agent Toolkit rules -->
