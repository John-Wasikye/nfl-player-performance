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
| 2 | **The staleness alarm never fires.** CloudWatch's default missing-data treatment is `missing`, and when every point in the window is missing the alarm goes to `INSUFFICIENT_DATA`, not `ALARM`. A pipeline that dies completely stops emitting - which is exactly the case the alarm exists for | `--treat-missing-data breaching` on every "did it run" and "is it fresh" alarm. Verified against the AWS docs table: all-missing + `breaching` = `ALARM` | **done 2026-10-05** (`monitoring.tf`; success counted by the rule's `TriggeredRules` metric, seen at 1.0 after a real run; alarm fired by hand, email arrived) |
| 3 | Unconfirmed SNS subscription delivers nothing while the alarm looks configured | Publish a test message to the topic and watch an email arrive. Console must show the subscription **Confirmed** | step 12 |
| 4 | An alarm action pointing at a deleted or mistyped SNS topic. AWS documents that CloudWatch "doesn't test or validate the actions that you specify, nor does it detect any Amazon SNS errors resulting from an attempt to invoke nonexistent actions" - so the alarm reports healthy forever | `set-alarm-state --state-value ALARM` on every alarm once, and confirm the email. This is the only way to prove the whole path | step 12, step 15 |
| 5 | `ActionsEnabled: false` - the alarm changes state and tells nobody | Assert `ActionsEnabled` is true in `describe-alarms`; Terraform sets it explicitly rather than by default | **done 2026-10-05** (`actions_enabled = true`, checked in `describe-alarms`) |

### The pipeline reporting success while doing nothing

| # | How it fails quietly | What makes it loud | Status |
|---|---|---|---|
| 6 | The ingest's "skip if the source has not changed" check wrongly concludes nothing changed, so the run exits 0 having published last week's numbers as current | `_freshness_problems` in `publish.py`, inside the existing validation gate, so nothing is written when it trips. Check A: a regular-season game kicked off more than `STALE_AFTER_HOURS` ago and still has no result in `stg_schedules` | **done** |
| 7 | A model builds with far too few rows and publishes anyway | `MIN_RANKED` per position in `publish.py` already blocks this, and the validation gate means nothing is written when it trips | **done** |
| 8 | **The Fargate task never starts** - bad image pull, missing task role, subnet with no route out. Your code never runs, so no alarm based on your code's output can fire | An alarm on EventBridge `FailedInvocations`, plus an ECS task-state-change rule for non-zero exits. #2 catches it from the other side, which is why #2 is the keystone | **done 2026-10-05** (rules plus alarms; a task run with an invalid command exited 2 and the failure email arrived) |
| 9 | A dbt test silently does not run because its model was excluded from the selector. This already happened once here, with the `FIXTURELESS` constant | The exclusion is gone and the whole graph is tested again. Keep `dbt build` failing the run on any test failure, and treat a drop in the test count as a defect | **done**, keep |
| 10 | The published week is not the week you think it is - dbt or the publish lagging the raw data, so the rankings silently stop a week short | Check B of `_freshness_problems`: a week whose result has been settled longer than the threshold must be covered by the rankings | **done** |

### Records and publishing

| # | How it fails quietly | What makes it loud | Status |
|---|---|---|---|
| 11 | A conditional write returns 412, the code shrugs, and a changed forecast is quietly discarded | On 412, fetch the stored object and compare. Identical numbers log and continue; different numbers **raise**. Never log-and-continue on a difference | `storage-design.md` decision 3 |
| 12 | The git mirror action fails, locked predictions stop reaching the repo, and the public record quietly stops growing | GitHub notifies on workflow failure - confirm that setting is on. Add a check comparing the newest locked week in S3 with the newest in git | step 18 |
| 13 | The warehouse snapshot upload fails, so ad-hoc tasks fall back to rebuilding. Graceful, and therefore invisible | Log the fallback at warning level and count it; a persistent fallback means the upload is broken. Nothing to instrument yet: the snapshot upload and the fallback are both written in the storage refactor (step 14 prerequisite), `snapshot.py` logs every fallback with the fixed token `WAREHOUSE_SNAPSHOT_FALLBACK` and a failed upload with `WAREHOUSE_SNAPSHOT_UPLOAD_FAILED` (the run still publishes, then exits non-zero). Tests force both failures and assert the token and the count. **Still to do in step 15:** a CloudWatch metric filter on each token and an alarm on the count, with `treat_missing_data = "notBreaching"` for these two (no event is the healthy state, the opposite of the staleness alarm) | **done 2026-10-05**: log metric filters and alarms exist in `monitoring.tf`, both fired by hand and the emails arrived. The log-token path itself (a real fallback) has not been exercised |
| 14 | The publish gate correctly refuses bad data, so the **old** data stays live and the site shows stale rankings as though current | The stale-data banner must be driven by the `meta.json` timestamp, and an e2e test must prove it appears. Also alarm on "published but not refreshed" | **banner verified 2026-10-05** (e2e: appears at 37h on any page, absent at 35h, follows `generated_at` not `data_as_of`; removing the banner fails the tests). The alarm is step 15 |
| 15 | An S3 lifecycle rule expires raw snapshots that are still needed. Object Lock protects the records bucket, not `nfl-raw` | Keep lifecycle rules in Terraform where they are reviewable, and leave the current season's snapshots out of any expiry | step 13 |

### The website

| # | How it fails quietly | What makes it loud | Status |
|---|---|---|---|
| 16 | The browser's fetch of `/data/v1` fails and the page renders empty rather than wrong-looking | Explicit empty, error and loading states exist and are covered by the e2e suite | **done** |
| 17 | A schema change breaks the contract between `contract.py` and `web/lib/types.ts` | `SCHEMA_VERSION` must be bumped on any contract change; the publish gate validates against the schema | **done** |
| 18 | **A forecast is locked after kickoff.** `lock_week` writes whatever it is given, so a late scheduled run would stamp a forecast made during the games as written before them, and the Report card's central claim would be false with nothing erroring | `predict/kickoff.py` and `--lock-when-due`: lock only when the week's first kickoff is within 24 hours and more than 30 minutes away; an existing lock is published, never recomputed; an unlocked week past its kickoff, or one whose kickoff cannot be established, exits 1 and writes nothing, which the task-failed rule emails. The kickoff estimate errs early (UTC-4 all year) so doubt can only refuse. 25 tests, and the 5 that assert a refusal were each seen to fail with the guard disabled. Seen working on AWS 2026-10-05: week 4, never locked, was refused | **done 2026-10-05** |

### How the freshness gate is built

Both checks live in `_freshness_problems` and append to the same `problems` list the rest of the
validation gate uses, so a stale run writes nothing at all and the previously published data stays
live rather than being overwritten with something older.

Four decisions worth keeping:

- **One threshold for both checks** (`STALE_AFTER_HOURS = 48`). It also absorbs the ordinary case of
  nflverse publishing a schedule result before the weekly player stats that go with it, which would
  otherwise be a false alarm on check B.
- **Errors lean toward silence being *late*, never toward false alarms.** `kickoff_et` is a naive
  Eastern timestamp, and converting it properly would mean depending on a timezone database
  (`zoneinfo` needs `tzdata` on Windows) for at most an hour of precision against a 48-hour
  threshold. The fixed `EASTERN_TO_UTC_HOURS = 5` makes every game look up to an hour more recent
  than it was, which can only delay a complaint. A game missing its kickoff time falls back to the
  date at end of day for the same reason.
- **Nothing is skipped for being unparseable.** A game with neither a kickoff nor a date is reported
  as a problem rather than filtered out of the query, because a row the check silently drops is
  exactly the hole this rule exists to close.
- **A missing `stg_schedules` is a failure, not a pass.** A check that cannot run must never count as
  a check that passed, so the test fixture gained a schedule table rather than the code gaining a
  "skip if absent" branch.

Nine tests cover it, including the three cases that must *not* block a publish: a game still in
progress on a Sunday run, preseason and playoff games, and the offseason. The six that assert a
failure were each confirmed to fail when the check is disabled, so none of them passes for an
unrelated reason.

## What to carry into every later step

- Any new alarm gets `treat_missing_data = "breaching"` unless there is a written reason not to.
- Any new alert path gets fired on purpose once, and the notification is seen.
- Any new "skip because nothing changed" optimisation gets a freshness assertion next to it. A cache that
  silently serves stale data is the same bug as #6.
- Any new graceful fallback gets a log line and a counter. A fallback nobody can see is a failure nobody
  can find - that is #13.
- Prefer raising to logging whenever the alternative is continuing with data that might be wrong.
