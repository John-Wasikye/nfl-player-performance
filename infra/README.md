# Infrastructure

Terraform for the AWS deployment. Region us-east-1, CLI profile `nfl_player_stats`. For what to do when an
alert email arrives, see `docs/operations.md`.

- `bootstrap/` creates the state bucket once, with local state.
- The files here create the raw, records and site buckets, the ECR repository and the task roles.

```powershell
aws sso login --profile nfl_player_stats
$env:AWS_PROFILE = "nfl_player_stats"   # the code names no profile, so CI can use its own role
cd infra/bootstrap; terraform init; terraform apply
cd ..; terraform init; terraform plan; terraform apply
```

Also here: the ECS cluster and task (`ecs.tf`), the daily schedule and alarms (`monitoring.tf`), the CloudFront
distribution in front of the private site bucket (`cloudfront.tf`), and the certificate for
`nflstats.johnwasikye.com` (`domain.tf`). DNS lives at Cloudflare, so two records are added there by hand: the
certificate validation record and a CNAME from `nflstats` to the distribution, both set to DNS only.

`run-task.ps1` runs the pipeline task on demand with any command, for example `.un-task.ps1 backtest`.

## CI/CD (`github.tf`, `.github/workflows/`)

GitHub Actions reaches AWS through OIDC: no access key exists anywhere. Each run presents a short-lived
signed token and AWS checks that it names this repository and the expected ref.

- `ci.yml` runs on every push and pull request: lint and tests, the web suite, and `terraform fmt` and
  `validate`. None of it needs AWS.
- `plan.yml` runs `terraform plan` on pull requests that touch `infra/`, as the read-only `github-plan`
  role (cannot change anything, cannot read the data buckets). The plan appears on the run summary.
- `deploy.yml` runs on merge to `main` as the `github-deploy` role: it pushes the pipeline image (`:latest`
  and the commit SHA) and uploads the site. That role cannot change infrastructure, touch IAM or billing,
  read the records, or overwrite `data/v1/`.

Terraform itself is still applied by hand. The only repository secret is `AWS_ACCOUNT_ID`, stored so the
account number stays out of the public logs; it grants nothing.

`main` is protected: changes arrive by pull request and the `test`, `web` and `infra` checks must pass.

The daily task runs `nfl-pipeline daily` from the `:latest` image. Its schedule, alarms and the
kickoff guard that refuses a late lock are described in `docs/no-silent-failures.md`.

The $5 budget and billing alarm were made by hand and are not managed here.
