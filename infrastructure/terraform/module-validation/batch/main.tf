variable "test_id" { type = string }

data "aws_region" "current" {}

locals {
  name = "davdeploy-${var.test_id}"
  tags = { ManagedBy = "terraform", Purpose = "davdeploy-module-validation", TestId = var.test_id }
}

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
  name              = "/davdeploy/module-validation/${var.test_id}/batch"
  retention_in_days = 1
  tags              = local.tags
}
module "batch" {
  source             = "../../modules/batch-compute"
  name               = local.name
  service_role_arn   = aws_iam_role.batch_service.arn
  instance_role_arn  = aws_iam_role.task_execution.arn
  subnet_ids         = slice(data.aws_subnets.default.ids, 0, 2)
  security_group_ids = [aws_security_group.batch.id]
  image              = "public.ecr.aws/amazonlinux/amazonlinux:2023"
  log_group_name     = aws_cloudwatch_log_group.batch.name
  region             = data.aws_region.current.name
  tags               = local.tags
  depends_on         = [aws_iam_role_policy_attachment.batch_service, aws_iam_role_policy_attachment.task_execution]
}
output "job_queue_arn" { value = module.batch.job_queue_arn }
