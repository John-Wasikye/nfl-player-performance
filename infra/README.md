# Infrastructure

Terraform for the AWS deployment (build-plan step 13). Region us-east-1, CLI profile `nfl_player_stats`.

- `bootstrap/` creates the state bucket once, with local state.
- The files here create the raw, records and site buckets, the ECR repository and the task roles.

```powershell
aws sso login --profile nfl_player_stats
cd infra/bootstrap; terraform init; terraform apply
cd ..; terraform init; terraform plan; terraform apply
```

Not here yet: ECS cluster and task definition (step 14), EventBridge and alarms (step 15), CloudFront,
the GitHub OIDC role (step 18). The $5 budget and billing alarm were made by hand in step 12 and are not
managed here.
