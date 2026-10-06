# Infrastructure

Terraform for the AWS deployment (build-plan step 13). Region us-east-1, CLI profile `nfl_player_stats`.

- `bootstrap/` creates the state bucket once, with local state.
- The files here create the raw, records and site buckets, the ECR repository and the task roles.

```powershell
aws sso login --profile nfl_player_stats
cd infra/bootstrap; terraform init; terraform apply
cd ..; terraform init; terraform plan; terraform apply
```

Also here: the ECS cluster and task, the daily schedule and alarms (`monitoring.tf`), and the CloudFront
distribution in front of the private site bucket (`cloudfront.tf`). Until the custom domain exists (step 19)
the site is on the distribution's own `*.cloudfront.net` address (`terraform output site_url`).

Deploy the website with `cd web; npm run build; AWS_PROFILE=nfl_player_stats bash scripts/deploy-site.sh`.
It leaves `data/v1/` alone, because the pipeline owns that prefix. Each new pipeline image needs a new
`image_tag` (ECR tags are immutable).

Not here yet: the GitHub OIDC role (step 18). The $5 budget and billing alarm were made by hand in step 12 and are not
managed here.
