# Operations

How the deployed system runs, where things are, and what to do when something goes wrong. Written
2026-10-06. Terraform in `infra/` is the source of truth for every name below.

## What runs, and when

EventBridge starts one Fargate task every day at **15:00 UTC**. That is 11:00 AM Eastern while daylight
time lasts, and 10:00 AM after the clocks change on 2026-11-01. The task runs `nfl-pipeline daily`:

1. `run`: ingest the nflverse files, rebuild the warehouse with dbt (158 checks), validate, publish the
   JSON, upload the warehouse snapshot.
2. `predict --lock-when-due`: grade any finished locked weeks, project the coming week, and lock it only if
   its first kickoff is more than 30 minutes away and less than 24 hours away.

The task takes about 90 seconds and costs a few cents. If step 1 fails, step 2 does not run.

A week is locked once, on the run that falls inside that window. For a Thursday night opener that is
Thursday's 15:00 UTC run, about nine hours before kickoff. For a week whose first game is Sunday at 1:00 PM
Eastern it is that Sunday's run, and Saturday's if the first game is the early London kickoff.

## Where things are

| Thing | Name |
|---|---|
| Site | https://nflstats.johnwasikye.com (CloudFront distribution `E1OZ5WDKRFMJ25`) |
| Buckets | `jw-nfl-player-stats-raw`, `-records`, `-site`, `-tfstate` |
| Cluster, task definition | `nfl-player-performance`, `nfl-pipeline` |
| Image | ECR repository `nfl-player-performance`, tags `latest` and the commit SHA |
| Logs | CloudWatch log group `/ecs/nfl-pipeline`, streams `pipeline/pipeline/<task id>` |
| Alert topic | SNS `nfl-pipeline-alerts`, emailing the address in `infra/monitoring.tf` |
| Region and profile | us-east-1, SSO profile `nfl_player_stats` |

Sign in with `aws sso login --profile nfl_player_stats`, then `$env:AWS_PROFILE = "nfl_player_stats"`.
The session lasts about 12 hours.

## When an email arrives

| Email | What it means | What to do |
|---|---|---|
| `NFL pipeline task FAILED ... stopCode=EssentialContainerExited` | The task ran and exited non-zero. | Read the log (below). The last lines say which step failed. |
| `NFL pipeline task FAILED ... TaskFailedToStart` | The container never started: image pull, role or networking. | Check the ECR image exists and the task definition's roles in `infra/ecs.tf`. |
| Alarm `nfl-pipeline-no-success-in-26h` | No run has finished with exit code 0 for 26 hours. | Find out why the runs fail or stop arriving. Check the schedule rule is `ENABLED`. |
| Alarm `nfl-pipeline-rule-delivery-failed-*` | EventBridge could not start the task or deliver an event. | Check the rule's target and the scheduler role in `infra/monitoring.tf`. |
| Alarms `nfl-pipeline-fallback`, `nfl-pipeline-upload_failed` | The warehouse snapshot fell back to a rebuild, or its upload failed. | Look for `WAREHOUSE_SNAPSHOT_FALLBACK` or `WAREHOUSE_SNAPSHOT_UPLOAD_FAILED` in the log. |

Messages you may find in the log, and what they mean:

- `run stopped: dbt build failed, so nothing was published`: a data test failed. The old data stays live.
- `validation failed with N problem(s); nothing was published`: the publish gate refused the data. It lists
  the problems, including stale data. The old data stays live.
- `predict failed: 2026 week N was never locked and its first kickoff ... has passed`: the week missed its
  window. Nothing was locked, and that week will not be graded. It repeats each day until the week ends.
- `predict failed: ... week N is scheduled but no players could be projected`: the roster for that week is
  not published yet, so there is nothing to project or lock. See "Known gaps".
- `predict refused: ... already locked with different projections`: a locked week was about to be changed.
  This needs a person. Do not overwrite it.

## Reading a log

```powershell
$task = "<task id from the email>"
aws logs get-log-events --log-group-name /ecs/nfl-pipeline --log-stream-name "pipeline/pipeline/$task" --query "events[].message" --output text
```

## Run something by hand

`infra/run-task.ps1` starts the same task with a different command, waits, and prints how it ended.

```powershell
cd infra
.\run-task.ps1 daily               # what the schedule runs
.\run-task.ps1 run                 # ingest, build and publish, no projections
.\run-task.ps1 predict             # project the coming week without locking it
.\run-task.ps1 backtest            # score the rankings; writes backtest/summary.json to the raw bucket
.\run-task.ps1 experiment          # write the failure report for the last scored week
```

To lock a week yourself, run `.\run-task.ps1 predict --lock` **before that week's first kickoff**. A locked
week cannot be rewritten, which is what makes the report card meaningful.

## Changing things

- **Code or site:** open a pull request. `main` is protected, so `test`, `web` and `infra` must pass. Merging
  deploys the image (`latest` and the commit SHA) and the site.
- **Infrastructure:** edit `infra/`, open a pull request (CI posts the plan), then apply from the laptop with
  `terraform apply`. CI never applies.
- **After changing the image:** the next scheduled run uses it. To publish sooner, run `.\run-task.ps1 daily`.
- **A page looks stale after a deploy:** CloudFront caches pages for a few minutes. Clear it with
  `aws cloudfront create-invalidation --distribution-id E1OZ5WDKRFMJ25 --paths "/*"`.

## Known gaps

- **Between one week ending and the next week's roster appearing**, nothing can be projected, because the
  player list for a week comes from nflverse's weekly roster file. The one refresh I have seen was at 11:58 AM
  Eastern on 2026-10-05, after the 11:00 AM run, so a roster published that day is seen the next day. How soon
  after a week ends the next roster appears is not yet known; watch it in week 5. The run notes the gap and exits 0 while
  the next kickoff is more than a day away, and fails loudly once it is inside a day. The projections page keeps
  showing the finished week's projections until then. If week 5's roster turns out to arrive too late for
  Thursday, the options are a fallback to the newest roster week, or a second daily run.
- **The git mirror of locked forecasts is not built.** S3 holds the authoritative copy. See
  `no-silent-failures.md` item 12.
- **No frozen comparison model is fitted**, so the report card cannot yet show improvement over time.
- **The analyst session** that proposes one candidate feature a week still runs on the laptop, in Claude
  Code. Moving it to AWS is described in the build plan, section 19.
