# Storage design: running on an ephemeral filesystem

Decided 2026-10-01, before any Terraform was written, and **confirmed by the owner the same day**.
This governs `config.py`, `storage.py`, `dbt/profiles.yml` and `predict/weekly.py`, and it is the thing
to read before changing where any file lives.

A standing goal shaped these choices: **as little as possible should need the owner's laptop.** Only the
weekly Claude analyst session stays local, and section "What stays on the laptop" says why.

A Fargate task starts with an empty disk and loses it on exit. Today `config.py` keeps
`warehouse_path`, `predictions_dir` and `ledger_path` as local filesystem paths, and the `Storage`
local/S3 abstraction covers only the raw ingest. So "deploy to AWS" is not a config change until the
question below is answered.

## The organising question

Every piece of state is one of two things, and the two get opposite treatment:

- **Derived** - reproducible from code plus raw data. Disposable. Correctness comes from being able
  to rebuild it, so it needs no protection at all.
- **A record** - its value *is* that it cannot change after the fact. Locked predictions and the
  experiment ledger are the only records in this project, and they are the reason the Report card
  means anything. These need an integrity mechanism, not a convention.

Confusing the two is how a project like this quietly starts lying. A graded forecast that a later run
can rewrite is not evidence.

| State | Size today | Class | Home on AWS |
|---|---|---|---|
| Raw nflverse snapshots | 140 MB | source of truth, immutable + dated | `nfl-raw`, versioned, lifecycle expires ancient snapshots |
| `warehouse.duckdb` | 163 MB | derived | rebuilt on the task's local disk each run, then **published to `nfl-raw/warehouse/` as a read-only snapshot** for ad-hoc tasks |
| Published JSON | 1.6 MB | derived, but serves the site | `nfl-site` under `data/v1/` |
| Locked weekly predictions | ~60 KB/week | **record** | `nfl-records`, write-once (see below) |
| Experiment ledger | 3.3 KB | **record** | `nfl-records`, plus a git mirror |
| dbt seeds (ranking config) | tiny | code | git, baked into the image |
| Backtest summary | 4 KB | derived | `nfl-site` under `data/v1/` with the rest |

## Decision 1: always rebuild, then publish a read-only snapshot

The daily task **rebuilds the warehouse from raw on every run** and never reads a previous copy. When
the build succeeds it **uploads the finished file** to `nfl-raw/warehouse/`. Ad-hoc tasks download that
snapshot and run read-only; they never upload.

Why rebuild rather than reuse:

- Every model is `+materialized: table` and nothing is incremental, so `dbt build` already recreates
  the entire graph from raw plus seeds. The warehouse holds nothing that is not reproducible.
- Reusing yesterday's file makes the daily run depend on it being correct. A stale or corrupted
  warehouse then produces wrong output that looks fine, which is the worst failure mode available.
- A DuckDB file has no concurrent-writer story, so a retried or overlapping task could corrupt a
  shared file.
- Fargate includes 20 GB of ephemeral storage by default. 163 MB plus query spill is nowhere near it.

Why publish a snapshot anyway: so that `backtest` and `experiment` can run **in AWS** without each one
paying a full rebuild first. Exactly one writer (the daily task) and many read-only readers, so the
corruption hazard above does not apply. If the snapshot is missing or unreadable, a reader rebuilds
from raw instead of failing.

Cost: 163 MB in S3 is roughly half a cent a month.

Accepted consequence: the daily run always pays a full dbt build. That is already what
`nfl-pipeline run` does locally, and the cost estimate in the build plan assumed it.

### Corollary: `backtest` and `experiment` move to AWS too

They are CPU work on the same image, so they become **on-demand Fargate tasks** rather than terminal
commands - same image, different entry command, triggered from the CLI or a GitHub Actions
"run workflow" button. Their output (`docs/backtest.md`, `docs/last-week.md`) is written to S3 and the
git mirror in decision 4 brings it into the repo. This is the point of the snapshot above.

## Decision 2: dbt reads raw straight from S3

Set `RAW_ROOT=s3://<raw-bucket>/raw`. The `latest_raw` macro already reads
`read_parquet('{{ var("raw_root") }}/<dataset>/**/*.parquet', filename = true)`; DuckDB's `httpfs`
reads and globs `s3://` paths, and `filename = true` returns the full `s3://` URL, so the existing
`regexp_extract` on `ingest_date=` and `season=` keeps working untouched. The `raw_root` var and its
"or an s3:// path once AWS is set up" comment in `dbt_project.yml` were written for this.

`dbt/profiles.yml` grows `extensions: [httpfs]` and a second target:

- `dev` - local files, exactly as today.
- `aws` - a `secrets:` entry of `type: s3` with `provider: credential_chain`, so the **Fargate task
  role** supplies credentials. No access keys anywhere.
- MinIO keeps working with an explicit key/secret plus `endpoint`, `url_style: path`, `use_ssl: false`.

Raw then never lands on the task's disk at all; only the warehouse does.

## Decision 3: write-once is enforced, not assumed

`lock_week` currently checks `path.exists()` and then writes. On S3 that pattern is both racy and
unenforced. Two **complementary** controls replace it, and both are needed:

1. **Conditional write.** `PutObject` with `If-None-Match: "*"` creates the object only if the key is
   absent, and returns **412 Precondition Failed** if it already exists. It is atomic, needs only
   `s3:PutObject`, and is strictly stronger than the current check. This is what prevents a second
   version from ever being created.
2. **Versioning plus Object Lock in governance mode**, with a retention period. This is what prevents
   the first version from being deleted or lifecycle-expired.

They are not redundant: Object Lock protects *a version* and explicitly does not stop new versions
being written, while a conditional write does not stop a delete. Neither alone gives write-once.

**Governance mode, not compliance - confirmed by the owner.** Overriding governance needs the `s3:BypassGovernanceRetention`
permission plus an explicit request header, and the override lands in CloudTrail - that is
tamper-*evident*, which is the property this project actually claims. Compliance mode cannot be
overridden by anyone including the account root, and AWS documents the only early escape as deleting
the AWS account. Too sharp an edge for a one-person project where a bad write is a realistic Tuesday.

Set `object_lock_enabled` when Terraform **creates** the bucket; retrofitting it onto an existing
bucket is awkward at best.

Existing semantics are preserved exactly: re-locking a week with identical numbers is fine, because
pipeline runs get retried; re-locking with different numbers raises. On a 412, fetch the stored object
and compare - identical means log and return it, different means raise, same as today.

## Decision 4: git stays the public copy of the records (confirmed by the owner)

The locked files and the ledger are in git because a reader can verify them without trusting AWS or
the author. That is worth keeping, and a Fargate task cannot commit to git.

So: **S3 is the runtime store, git is the published record.** A scheduled GitHub Actions job pulls new
locked weeks and the ledger out of S3 and commits them. If the mirror fails, the authoritative object
still exists in S3 under Object Lock and nothing is lost - the mirror is for publication, not
durability.

## Decision 5: `Storage` grows two methods rather than a second abstraction

The protocol is `put_bytes` / `get_bytes`. Add:

- `put_bytes_if_absent(key, data) -> bool` - S3 passes `IfNoneMatch="*"` and maps 412 to `False`.
  Local uses `os.open(..., O_CREAT | O_EXCL)` and maps `FileExistsError` to `False`. Note it must
  **not** reuse the temp-file-then-`os.replace` pattern from `put_bytes`: `os.replace` overwrites,
  which is the exact opposite of what is wanted here.
- `list_keys(prefix) -> list[str]` - needed to discover which weeks are locked. S3 paginates
  `list_objects_v2`; local uses `rglob`.

Then `lock_path` / `lock_week` / `load_locked` and `Ledger` take a `Storage` and a key prefix instead
of a `Path`. **Built 2026-10-05, with one change from this plan:** the records get a bucket of their own,
so there is no `predictions_prefix`. `config.py` has `s3_records_bucket` and `ledger_key`, and
`build_records_storage()` returns a `LocalStorage` rooted at `<data>/predictions` locally (the same on-disk
layout as before: `<season>/week_NN.json` and `ledger.json`) or an `S3Storage` on the records bucket.
`warehouse_path` stays a local path, because decision 1 makes it ephemeral on purpose.

Tests stay offline on the fakes in `pipeline/tests/conftest.py`, and gain a **shared contract test run
against both backends**: a second write is refused, an identical rewrite reports already-present, and
listing returns what was written. A fake that quietly overwrites would make this whole design
worthless, so the fake is held to the same contract as S3.

## Buckets

One bucket per lifecycle, because the policies genuinely differ:

| Bucket | Contents | Policy |
|---|---|---|
| `nfl-raw` | raw snapshots, ingest manifests, and the `warehouse/` snapshot | versioned; lifecycle expires old snapshots and noncurrent versions, keeping only the few most recent warehouse copies |
| `nfl-records` | locked predictions, ledger | versioned + **Object Lock (governance)**; no expiry; tiny |
| `nfl-site` | the static site **and** published JSON under `data/v1/` | versioned; CloudFront OAC origin; short noncurrent expiry |
| `nfl-tfstate` | Terraform state | versioned, encrypted, private, Terraform-native locking |

All four get S3 Block Public Access; CloudFront OAC is the only reader of `nfl-site`.

**Built 2026-10-05.** Publishing uses the `data/v1/` prefix, and `build_site_storage()` returns the site bucket on S3 or `<data>/site` locally, so the key layout is identical in both places (locally the files land in `data/site/data/v1/`, which `web/scripts/sync-data.mjs` reads). `snapshot.py` uploads the warehouse to `nfl-raw/warehouse/warehouse.duckdb` after each build; `dbt/profiles.yml` has `aws` (credential chain) and `minio` targets, chosen by `dbt_target()`. The `aws` target is **untested against real S3** until the account exists: on a machine with no AWS credentials it fails at connection, which is the right way to fail.

**Publishing moves to the `data/v1/` prefix of the site bucket**, replacing `published/v1`. The
website already fetches from `/data/v1`, so one bucket and one CloudFront origin serves both the HTML
and the JSON - no second origin, no extra cache behaviour, and the path the browser requests is the
path the publish step wrote. `meta.json` is still written last.

## What stays on the laptop, and why

After this design, the only thing that still needs the owner's machine is the **weekly Claude analyst
session** - the part that reads `docs/last-week.md` and writes one candidate into
`predict/proposals.py`. It stays in Claude Code deliberately, because phase 1C set no
`ANTHROPIC_API_KEY`: Claude runs inside the Pro plan at no per-token cost. Automating it in AWS means
paying API rates, and as an interactive multi-turn session that is roughly **$2-6 a week** - several
times the entire rest of the project's AWS bill. See BUILD_PLAN.md section 13 for the breakdown and
the cheaper single-call shape, if that ever becomes worth it.

Everything else - the daily pipeline, the weekly predict/lock/grade, the backtest, and the experiment
harness - runs in AWS. Website development and the test suites are development work and stay local by
nature.

### Later: moving the analyst session to AWS

The owner intends to move it eventually. The researched route is Claude Code on Amazon Bedrock, authenticated by the Fargate task role, so no API key or secret is needed and the storage design above does not change: the task reads the warehouse snapshot and writes a proposed change to a pull request. It would cost about $1-3 a week on Sonnet or $2-6 on Opus, paid at API rates. Running it on the Pro subscription from AWS is not recommended, because Anthropic describes subscription login as for ordinary individual use. The write-up is in the build plan, section 19. Nothing here is built.

## What this does not decide

- Whether `ranking_config.csv` stays at 70/30 (open decision, unrelated to storage).
- Glue and Athena, which are deferred past launch and read `nfl-raw` when they arrive.
