# Nothing fails silently

A standing rule for this project, set 2026-10-01. Every failure must announce itself. Where that is not
possible, the *absence* of a signal must itself be the alarm.

This matters more here than in most projects. The pipeline runs unattended once a day, publishes numbers
that are supposed to be evidence, and grades its own predictions. A component that breaks quietly does
not produce an outage - it produces **confidently wrong output**, which is worse, because the Report card
keeps looking credible while the thing underneath it has stopped working.

## Two principles

**1. Test it, don't inspect it.** Confirming a thing is *configured* is much weaker than making it
*fire*. Every alarm gets deliberately triggered once, and the notification is seen arriving. An untested
alert path is an assumption, not a safeguard.

**2. Fail closed.** Where a signal can go missing, treat missing as broken rather than as fine. Silence
is the most common symptom of total failure, so silence must never read as health.

## The inventory

Status is one of: **done** (already true in the code), **step N** (handled in that build-plan step), or
**to do** (needs work that is not yet scheduled).

### Monitoring that isn't monitoring

| # | How it fails quietly | What makes it loud | Status |
|---|---|---|---|
| 1 | Billing alarm created outside us-east-1 - billing metrics publish only there, so the metric never appears and the alarm never evaluates | Create in us-east-1; verify `describe-alarms` returns it and it leaves `INSUFFICIENT_DATA` | step 12 |
| 2 | **The staleness alarm never fires.** CloudWatch's default missing-data treatment is `missing`, and when every point in the window is missing the alarm goes to `INSUFFICIENT_DATA`, not `ALARM`. A pipeline that dies completely stops emitting - which is exactly the case the alarm exists for | `--treat-missing-data breaching` on every "did it run" and "is it fresh" alarm. Verified against the AWS docs table: all-missing + `breaching` = `ALARM` | step 15 |
| 3 | Unconfirmed SNS subscription delivers nothing while the alarm looks configured | Publish a test message to the topic and watch an email arrive. Console must show the subscription **Confirmed** | step 12 |
| 4 | An alarm action pointing at a deleted or mistyped SNS topic. AWS documents that CloudWatch "doesn't test or validate the actions that you specify, nor does it detect any Amazon SNS errors resulting from an attempt to invoke nonexistent actions" - so the alarm reports healthy forever | `set-alarm-state --state-value ALARM` on every alarm once, and confirm the email. This is the only way to prove the whole path | step 12, step 15 |
| 5 | `ActionsEnabled: false` - the alarm changes state and tells nobody | Assert `ActionsEnabled` is true in `describe-alarms`; Terraform sets it explicitly rather than by default | step 13 |

### The pipeline reporting success while doing nothing

| # | How it fails quietly | What makes it loud | Status |
|---|---|---|---|
| 6 | The ingest's "skip if the source has not changed" check wrongly concludes nothing changed, so the run exits 0 having published last week's numbers as current | A freshness assertion in the publish gate: during the season, if the newest final game is older than a threshold, fail the publish | **to do** |
| 7 | A model builds with far too few rows and publishes anyway | `MIN_RANKED` per position in `publish.py` already blocks this, and the validation gate means nothing is written when it trips | **done** |
| 8 | **The Fargate task never starts** - bad image pull, missing task role, subnet with no route out. Your code never runs, so no alarm based on your code's output can fire | An alarm on EventBridge `FailedInvocations`, plus an ECS task-state-change rule for non-zero exits. #2 catches it from the other side, which is why #2 is the keystone | step 15 |
| 9 | A dbt test silently does not run because its model was excluded from the selector. This already happened once here, with the `FIXTURELESS` constant | The exclusion is gone and the whole graph is tested again. Keep `dbt build` failing the run on any test failure, and treat a drop in the test count as a defect | **done**, keep |
| 10 | The published week is not the week you think it is | Assert the published week equals the expected week in the validation gate | **to do** |

### Records and publishing

| # | How it fails quietly | What makes it loud | Status |
|---|---|---|---|
| 11 | A conditional write returns 412, the code shrugs, and a changed forecast is quietly discarded | On 412, fetch the stored object and compare. Identical numbers log and continue; different numbers **raise**. Never log-and-continue on a difference | `storage-design.md` decision 3 |
| 12 | The git mirror action fails, locked predictions stop reaching the repo, and the public record quietly stops growing | GitHub notifies on workflow failure - confirm that setting is on. Add a check comparing the newest locked week in S3 with the newest in git | step 18 |
| 13 | The warehouse snapshot upload fails, so ad-hoc tasks fall back to rebuilding. Graceful, and therefore invisible | Log the fallback at warning level and count it; a persistent fallback means the upload is broken | **to do** |
| 14 | The publish gate correctly refuses bad data, so the **old** data stays live and the site shows stale rankings as though current | The stale-data banner must be driven by the `meta.json` timestamp, and an e2e test must prove it appears. Also alarm on "published but not refreshed" | verify |
| 15 | An S3 lifecycle rule expires raw snapshots that are still needed. Object Lock protects the records bucket, not `nfl-raw` | Keep lifecycle rules in Terraform where they are reviewable, and leave the current season's snapshots out of any expiry | step 13 |

### The website

| # | How it fails quietly | What makes it loud | Status |
|---|---|---|---|
| 16 | The browser's fetch of `/data/v1` fails and the page renders empty rather than wrong-looking | Explicit empty, error and loading states exist and are covered by the e2e suite | **done** |
| 17 | A schema change breaks the contract between `contract.py` and `web/lib/types.ts` | `SCHEMA_VERSION` must be bumped on any contract change; the publish gate validates against the schema | **done** |

## What to carry into every later step

- Any new alarm gets `treat_missing_data = "breaching"` unless there is a written reason not to.
- Any new alert path gets fired on purpose once, and the notification is seen.
- Any new "skip because nothing changed" optimisation gets a freshness assertion next to it. A cache that
  silently serves stale data is the same bug as #6.
- Any new graceful fallback gets a log line and a counter. A fallback nobody can see is a failure nobody
  can find - that is #13.
- Prefer raising to logging whenever the alternative is continuing with data that might be wrong.
