# Two roles for the Fargate task, nothing else yet (the GitHub OIDC role arrives with CI/CD).
#   execution role: lets ECS pull the image and write logs. It acts before our code runs.
#   task role:      what our code may do, limited to its own buckets.

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    # Confused-deputy guard: only ECS tasks in this account may assume these roles.
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "nfl-pipeline-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name               = "nfl-pipeline-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "task" {
  # raw: ingest writes snapshots and the warehouse copy; dbt and backtest read them.
  statement {
    sid       = "RawReadWrite"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.raw.arn}/*"]
  }
  statement {
    sid       = "RawList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.raw.arn]
  }

  # records: get, put (including If-None-Match conditional writes) and list, never delete.
  # s3:BypassGovernanceRetention is withheld, so the task cannot override the lock.
  statement {
    sid       = "RecordsReadWrite"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.records.arn}/*"]
  }
  statement {
    sid       = "RecordsList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.records.arn]
  }
  statement {
    sid    = "RecordsNeverDelete"
    effect = "Deny"
    actions = [
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:BypassGovernanceRetention",
      "s3:PutBucketObjectLockConfiguration",
      "s3:PutObjectRetention",
    ]
    resources = [aws_s3_bucket.records.arn, "${aws_s3_bucket.records.arn}/*"]
  }

  # site: only the published JSON prefix. The static site itself is deployed by CI, not by this task.
  statement {
    sid       = "SitePublishedData"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.site.arn}/data/v1/*"]
  }
  # ListBucket is unrestricted so that reading a missing key returns 404 rather than 403.
  statement {
    sid       = "SiteList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.site.arn]
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "nfl-pipeline-buckets"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}
