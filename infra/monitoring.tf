# Daily schedule plus the alarms from docs/no-silent-failures.md (items 2, 4, 5, 8, 13, 14).
#
# "Did it succeed" is measured without touching the pipeline code: an EventBridge rule matches ECS task
# state changes that stopped with exit code 0, and the rule's own TriggeredRules metric counts them.
# Silence therefore reads as failure (treat_missing_data = "breaching"), which is what catches a pipeline
# that has died completely.

variable "alert_email" {
  type    = string
  default = "john.wasikye@gmail.com"
}

variable "schedule_expression" {
  description = "UTC. 15:00 is 11:00 EDT / 10:00 EST."
  type        = string
  default     = "cron(0 15 * * ? *)"
}

variable "stale_after_hours" {
  type    = number
  default = 26
}

locals {
  task_family_arn = aws_ecs_task_definition.pipeline.arn_without_revision
  task_match = {
    source      = ["aws.ecs"]
    detail-type = ["ECS Task State Change"]
  }
}

resource "aws_sns_topic" "alerts" {
  name = "nfl-pipeline-alerts"
}

# Created pending: the address has to click the confirmation link once, or nothing is ever delivered.
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

data "aws_iam_policy_document" "alerts_topic" {
  statement {
    sid       = "AllowEventBridgePublish"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  statement {
    sid       = "AllowCloudWatchAlarmPublish"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "alerts" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.alerts_topic.json
}

# ---- the daily run -------------------------------------------------------------------------------

data "aws_iam_policy_document" "events_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "nfl-pipeline-scheduler"
  assume_role_policy = data.aws_iam_policy_document.events_assume.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["ecs:RunTask"]
    resources = ["${local.task_family_arn}:*"]
    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.main.arn]
    }
  }
  statement {
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.task.arn, aws_iam_role.task_execution.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "run-pipeline-task"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_cloudwatch_event_rule" "daily" {
  name                = "nfl-pipeline-daily"
  description         = "Starts the pipeline task once a day"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "daily" {
  rule     = aws_cloudwatch_event_rule.daily.name
  arn      = aws_ecs_cluster.main.arn
  role_arn = aws_iam_role.scheduler.arn

  ecs_target {
    launch_type         = "FARGATE"
    task_definition_arn = local.task_family_arn
    task_count          = 1

    network_configuration {
      subnets          = data.aws_subnets.default.ids
      security_groups  = [aws_security_group.task.id]
      assign_public_ip = true
    }
  }
}

# ---- what the task did ---------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "task_succeeded" {
  name        = "nfl-pipeline-task-succeeded"
  description = "Pipeline task stopped with exit code 0. Counted by the staleness alarm."
  event_pattern = jsonencode(merge(local.task_match, {
    detail = {
      clusterArn        = [aws_ecs_cluster.main.arn]
      taskDefinitionArn = [{ prefix = "${local.task_family_arn}:" }]
      lastStatus        = ["STOPPED"]
      stopCode          = ["EssentialContainerExited"]
      containers        = { exitCode = [0] }
    }
  }))
}

# Fires for a non-zero exit, and for a task that never started (image pull, role, networking), where no
# container ran and so no exit code exists.
resource "aws_cloudwatch_event_rule" "task_failed" {
  name        = "nfl-pipeline-task-failed"
  description = "Pipeline task exited non-zero or failed to start"
  event_pattern = jsonencode(merge(local.task_match, {
    detail = {
      clusterArn        = [aws_ecs_cluster.main.arn]
      taskDefinitionArn = [{ prefix = "${local.task_family_arn}:" }]
      lastStatus        = ["STOPPED"]
      "$or" = [
        { containers = { exitCode = [{ "anything-but" = [0] }] } },
        { stopCode = ["TaskFailedToStart"] },
      ]
    }
  }))
}

resource "aws_cloudwatch_event_target" "task_failed_email" {
  rule = aws_cloudwatch_event_rule.task_failed.name
  arn  = aws_sns_topic.alerts.arn

  input_transformer {
    input_paths = {
      task   = "$.detail.taskArn"
      code   = "$.detail.stopCode"
      reason = "$.detail.stoppedReason"
      at     = "$.detail.stoppedAt"
    }
    input_template = "\"NFL pipeline task FAILED. stopCode=<code> reason=<reason> stoppedAt=<at> task=<task>. Logs: log group /ecs/nfl-pipeline, region us-east-1.\""
  }
}

# ---- alarms --------------------------------------------------------------------------------------

# Item 2, the keystone: no successful run in the window. Every hourly point must be below 1, and a missing
# point counts as breaching, so a pipeline that has stopped emitting anything still alarms.
resource "aws_cloudwatch_metric_alarm" "no_recent_success" {
  alarm_name          = "nfl-pipeline-no-success-in-${var.stale_after_hours}h"
  alarm_description   = "No pipeline run has finished with exit code 0 recently."
  namespace           = "AWS/Events"
  metric_name         = "TriggeredRules"
  dimensions          = { RuleName = aws_cloudwatch_event_rule.task_succeeded.name }
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = var.stale_after_hours
  datapoints_to_alarm = var.stale_after_hours
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  actions_enabled     = true
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# Item 8 and item 4: an EventBridge rule that cannot deliver. Missing data is the healthy state here (the
# metric only exists when a failure happens), so notBreaching is deliberate; the staleness alarm above
# covers silence.
resource "aws_cloudwatch_metric_alarm" "failed_invocations" {
  for_each = {
    daily          = aws_cloudwatch_event_rule.daily.name
    task_succeeded = aws_cloudwatch_event_rule.task_succeeded.name
    task_failed    = aws_cloudwatch_event_rule.task_failed.name
  }

  alarm_name          = "nfl-pipeline-rule-delivery-failed-${each.key}"
  alarm_description   = "EventBridge rule ${each.value} failed to deliver to its target."
  namespace           = "AWS/Events"
  metric_name         = "FailedInvocations"
  dimensions          = { RuleName = each.value }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  actions_enabled     = true
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# Item 13: graceful fallbacks that would otherwise be invisible. Same missing-data reasoning.
resource "aws_cloudwatch_log_metric_filter" "snapshot" {
  for_each = {
    fallback      = "WAREHOUSE_SNAPSHOT_FALLBACK"
    upload_failed = "WAREHOUSE_SNAPSHOT_UPLOAD_FAILED"
  }

  name           = "nfl-pipeline-${each.key}"
  log_group_name = aws_cloudwatch_log_group.pipeline.name
  pattern        = "\"${each.value}\""

  metric_transformation {
    name      = each.value
    namespace = "NflPipeline"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "snapshot" {
  for_each = aws_cloudwatch_log_metric_filter.snapshot

  alarm_name          = "nfl-pipeline-${each.key}"
  alarm_description   = "The log token ${each.value.metric_transformation[0].name} appeared."
  namespace           = "NflPipeline"
  metric_name         = each.value.metric_transformation[0].name
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  actions_enabled     = true
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
