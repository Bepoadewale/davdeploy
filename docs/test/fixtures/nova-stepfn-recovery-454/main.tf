terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.100.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "= 2.7.1"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "account_id" {
  type = string
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.account_id]
}

data "aws_partition" "current" {}
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  prefix = "davdeploy-nova-stepfn-recovery-454-nov23a2"
  tags = {
    Product     = "davdeploy"
    Environment = "test"
    Purpose     = "nova-stepfn-recovery-454"
    TestRun     = "nov23a2"
    ManagedBy   = "Terraform"
  }
}

data "archive_file" "worker" {
  type        = "zip"
  source_file = "${path.module}/worker.py"
  output_path = "${path.module}/worker.zip"
}

resource "aws_iam_role" "worker" {
  name = "${local.prefix}-worker"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_lambda_function" "worker" {
  function_name    = "${local.prefix}-worker"
  role             = aws_iam_role.worker.arn
  runtime          = "python3.12"
  handler          = "worker.handler"
  filename         = data.archive_file.worker.output_path
  source_code_hash = data.archive_file.worker.output_base64sha256
  timeout          = 10
  memory_size      = 128
  tags             = local.tags
}

resource "aws_iam_role" "state_machine" {
  name = "${local.prefix}-sfn"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "state_machine" {
  name = "${local.prefix}-invoke-worker"
  role = aws_iam_role.state_machine.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = aws_lambda_function.worker.arn
    }]
  })
}

resource "aws_sfn_state_machine" "test" {
  name     = local.prefix
  role_arn = aws_iam_role.state_machine.arn
  type     = "STANDARD"
  definition = jsonencode({
    Comment = "Controlled failure and Catch recovery test"
    StartAt = "FailingTask"
    States = {
      FailingTask = {
        Type     = "Task"
        Resource = aws_lambda_function.worker.arn
        Catch = [{
          ErrorEquals = ["States.TaskFailed"]
          ResultPath  = "$.failure"
          Next        = "Recover"
        }]
        End = true
      }
      Recover = {
        Type = "Pass"
        Parameters = {
          should_fail      = false
          "marker.$"       = "$.marker"
          "failure_name.$" = "$.failure.Error"
        }
        Next = "RecoveryTask"
      }
      RecoveryTask = {
        Type     = "Task"
        Resource = aws_lambda_function.worker.arn
        End      = true
      }
    }
  })
  tags = local.tags

  depends_on = [aws_iam_role_policy.state_machine]
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.test.arn
}

output "state_machine_name" {
  value = aws_sfn_state_machine.test.name
}

output "prefix" {
  value = local.prefix
}
