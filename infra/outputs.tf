output "bucket_names" {
  value = local.buckets
}

output "ecr_repository_url" {
  value = aws_ecr_repository.pipeline.repository_url
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "task_execution_role_arn" {
  value = aws_iam_role.task_execution.arn
}

output "run_task_network" {
  description = "Values for aws ecs run-task."
  value = {
    cluster         = aws_ecs_cluster.main.name
    task_definition = aws_ecs_task_definition.pipeline.family
    subnets         = data.aws_subnets.default.ids
    security_group  = aws_security_group.task.id
  }
}
