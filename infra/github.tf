# How GitHub Actions gets into AWS without any stored key (OIDC).
#
# Each workflow run carries a short-lived signed token from GitHub that names the repository and the
# branch or event it is running for. AWS checks the signature and the conditions below, then issues
# credentials that expire in about an hour. There is no access key, so there is nothing in the
# repository or in GitHub's settings to leak or rotate. What is public is only these rules, and they
# grant nothing to anyone outside the named repository and ref.
#
# Two roles with different power:
#   github-plan    pull requests: can read the infrastructure to run `terraform plan`, nothing more.
#   github-deploy  main branch only: can push the pipeline image and the website, nothing else.
# Neither can touch IAM, billing, the records bucket, or the published data.

variable "github_repository" {
  type    = string
  default = "John-Wasikye/nfl-player-performance"
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_trust" {
  for_each = {
    plan   = "repo:${var.github_repository}:pull_request"
    deploy = "repo:${var.github_repository}:ref:refs/heads/main"
  }

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # An exact match, never a wildcard: any other repository, branch, tag or fork is refused.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [each.value]
    }
  }
}

# ---- pull requests: read-only ---------------------------------------------------------------------

resource "aws_iam_role" "github_plan" {
  name                 = "github-plan"
  assume_role_policy   = data.aws_iam_policy_document.github_trust["plan"].json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "github_plan_read" {
  role       = aws_iam_role.github_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# ReadOnlyAccess can read object contents. Planning only needs bucket configuration and the state
# file, so the data buckets are closed to it explicitly (an explicit deny beats any allow).
data "aws_iam_policy_document" "github_plan_limits" {
  statement {
    sid       = "NoDataReads"
    effect    = "Deny"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = [for arn in values(local.bucket_arns) : "${arn}/*"]
  }
}

resource "aws_iam_role_policy" "github_plan_limits" {
  name   = "no-data-reads"
  role   = aws_iam_role.github_plan.id
  policy = data.aws_iam_policy_document.github_plan_limits.json
}

# ---- main branch: ship the image and the site ------------------------------------------------------

resource "aws_iam_role" "github_deploy" {
  name                 = "github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.github_trust["deploy"].json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "PushPipelineImage"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
    ]
    resources = [aws_ecr_repository.pipeline.arn]
  }

  statement {
    sid       = "UploadSite"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]
  }
  statement {
    sid       = "ListSite"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.site.arn]
  }
  # The daily pipeline owns data/v1/. A site deploy must never be able to overwrite or delete it.
  statement {
    sid       = "NeverTouchPublishedData"
    effect    = "Deny"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.site.arn}/data/v1/*"]
  }

  statement {
    sid       = "RefreshCdn"
    actions   = ["cloudfront:CreateInvalidation"]
    resources = [aws_cloudfront_distribution.site.arn]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "ship-image-and-site"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}

output "github_plan_role_arn" {
  value = aws_iam_role.github_plan.arn
}

output "github_deploy_role_arn" {
  value = aws_iam_role.github_deploy.arn
}
