data "aws_region" "current" {}
data "aws_vpc" "default" { default = true }
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_iam_policy_document" "batch_service_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["batch.amazonaws.com"]
    }
  }
}
data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

locals {
  name = "davdeploy-nova-batch-retry-${var.run_id}"
  tags = {
    ManagedBy = "Terraform"
    Product   = "davdeploy"
    Purpose   = "nova-batch-retry-recovery-test"
    TestRun   = var.run_id
  }
}

resource "aws_iam_role" "batch_service" {
  name               = "${local.name}-service"
  assume_role_policy = data.aws_iam_policy_document.batch_service_assume.json
  tags               = local.tags
}
resource "aws_iam_role_policy_attachment" "batch_service" {
  role       = aws_iam_role.batch_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}
resource "aws_iam_role" "task_execution" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = local.tags
}
resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_security_group" "batch" {
  name_prefix = "${local.name}-"
  vpc_id      = data.aws_vpc.default.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}
resource "aws_cloudwatch_log_group" "batch" {
  name              = "/davdeploy/nova-batch-retry/${var.run_id}"
  retention_in_days = 1
  tags              = local.tags
}
resource "aws_batch_compute_environment" "batch" {
  compute_environment_name = local.name
  type                     = "MANAGED"
  state                    = "ENABLED"
  service_role             = aws_iam_role.batch_service.arn
  compute_resources {
    type               = "FARGATE"
    max_vcpus          = 1
    subnets            = slice(data.aws_subnets.default.ids, 0, 2)
    security_group_ids = [aws_security_group.batch.id]
  }
  tags       = local.tags
  depends_on = [aws_iam_role_policy_attachment.batch_service]
}
resource "aws_batch_job_queue" "batch" {
  name     = local.name
  state    = "ENABLED"
  priority = 1
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.batch.arn
  }
  tags = local.tags
}
resource "aws_batch_job_definition" "batch" {
  name                  = local.name
  type                  = "container"
  platform_capabilities = ["FARGATE"]
  retry_strategy {
    attempts = 2
  }
  container_properties = jsonencode({
    image            = "public.ecr.aws/amazonlinux/amazonlinux:2023"
    executionRoleArn = aws_iam_role.task_execution.arn
    command = [
      "sh",
      "-c",
      "printf 'attempt=%s\\n' \"$AWS_BATCH_JOB_ATTEMPT\"; test \"$AWS_BATCH_JOB_ATTEMPT\" -ge 2",
    ]
    networkConfiguration = { assignPublicIp = "ENABLED" }
    resourceRequirements = [
      { type = "VCPU", value = "0.25" },
      { type = "MEMORY", value = "512" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.batch.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "batch-retry"
      }
    }
  })
  tags       = local.tags
  depends_on = [aws_iam_role_policy_attachment.task_execution]
}

output "job_queue_name" { value = aws_batch_job_queue.batch.name }
output "job_definition_arn" { value = aws_batch_job_definition.batch.arn }
output "log_group_name" { value = aws_cloudwatch_log_group.batch.name }
