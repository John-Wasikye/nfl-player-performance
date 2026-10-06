# Fargate task for the pipeline. Runs in the default VPC's public subnets with a public IP, which
# avoids a NAT gateway (about $33 a month). The security group allows no inbound traffic at all.

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_ecs_cluster" "main" {
  name = "nfl-player-performance"
}

resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/ecs/nfl-pipeline"
  retention_in_days = 30
}

resource "aws_security_group" "task" {
  name        = "nfl-pipeline-task"
  description = "Pipeline task: outbound only"
  vpc_id      = data.aws_vpc.default.id

  egress {
    description = "HTTPS to nflverse, S3 and ECR"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "pipeline" {
  family                   = "nfl-pipeline"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name      = "pipeline"
    image     = "${aws_ecr_repository.pipeline.repository_url}:${var.image_tag}"
    essential = true
    command   = ["daily"]
    environment = [
      { name = "STORAGE_BACKEND", value = "s3" },
      { name = "S3_BUCKET", value = aws_s3_bucket.raw.id },
      { name = "S3_RECORDS_BUCKET", value = aws_s3_bucket.records.id },
      { name = "S3_SITE_BUCKET", value = aws_s3_bucket.site.id },
      { name = "AWS_DEFAULT_REGION", value = var.region },
      # The warehouse is rebuilt every run, so it lives on the task's own disk (docs/storage-design.md).
      { name = "WAREHOUSE_PATH", value = "/tmp/warehouse.duckdb" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.pipeline.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "pipeline"
      }
    }
  }])
}
