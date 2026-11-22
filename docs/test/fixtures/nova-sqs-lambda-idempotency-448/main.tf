terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.100.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "2.7.1"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

variable "consumer_version" {
  type        = string
  description = "Synthetic consumer package used by the isolated lifecycle test."
  default     = "v1"
  validation {
    condition     = contains(["v1", "v2"], var.consumer_version)
    error_message = "consumer_version must be v1 or v2."
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  test_id       = "nov22a1"
  prefix        = "davdeploy-nova-sqs-idem-448-${local.test_id}"
  queue_name    = local.prefix
  dlq_name      = "${local.prefix}-dlq"
  function_name = local.prefix
  table_name    = "${local.prefix}-idempotency"
  source_arn    = "arn:${data.aws_partition.current.partition}:sqs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${local.queue_name}"
  dlq_arn       = "arn:${data.aws_partition.current.partition}:sqs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${local.dlq_name}"
  test_tags = {
    Product     = "davdeploy"
    Environment = "test"
    Purpose     = "nova-sqs-lambda-idempotency-448"
    TestRun     = local.test_id
    ManagedBy   = "Terraform"
  }
}

data "archive_file" "consumer" {
  type        = "zip"
  source_file = "${path.module}/consumer_${var.consumer_version}.py"
  output_path = "${path.module}/consumer.zip"
}

resource "aws_sqs_queue" "dlq" {
  name                      = local.dlq_name
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [local.source_arn]
  })
  tags = local.test_tags
}

resource "aws_sqs_queue" "source" {
  depends_on                 = [aws_sqs_queue.dlq]
  name                       = local.queue_name
  visibility_timeout_seconds = 30
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = local.dlq_arn
    maxReceiveCount     = 5
  })
  tags = local.test_tags
}

resource "aws_dynamodb_table" "idempotency" {
  name                        = local.table_name
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "idempotency_key"
  deletion_protection_enabled = false

  attribute {
    name = "idempotency_key"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  tags = local.test_tags
}

resource "aws_iam_role" "consumer" {
  name = "${local.prefix}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.test_tags
}

resource "aws_iam_role_policy" "consumer" {
  name = "${local.prefix}-consumer-access"
  role = aws_iam_role.consumer.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
        ]
        Resource = local.source_arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = aws_dynamodb_table.idempotency.arn
      },
    ]
  })
}

resource "aws_lambda_function" "consumer" {
  function_name    = local.function_name
  role             = aws_iam_role.consumer.arn
  runtime          = "python3.12"
  handler          = "consumer_${var.consumer_version}.handler"
  filename         = data.archive_file.consumer.output_path
  source_code_hash = data.archive_file.consumer.output_base64sha256
  timeout          = 3
  memory_size      = 128

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.idempotency.name
    }
  }

  tags = local.test_tags
}

resource "aws_lambda_event_source_mapping" "consumer" {
  event_source_arn                   = aws_sqs_queue.source.arn
  function_name                      = aws_lambda_function.consumer.arn
  enabled                            = true
  batch_size                         = 1
  maximum_batching_window_in_seconds = 0
  depends_on                         = [aws_iam_role_policy.consumer]
}

output "source_queue_arn" {
  value = aws_sqs_queue.source.arn
}

output "source_queue_url" {
  value = aws_sqs_queue.source.url
}

output "dlq_queue_arn" {
  value = aws_sqs_queue.dlq.arn
}

output "dlq_queue_url" {
  value = aws_sqs_queue.dlq.url
}

output "table_name" {
  value = aws_dynamodb_table.idempotency.name
}

output "function_name" {
  value = aws_lambda_function.consumer.function_name
}

output "mapping_uuid" {
  value = aws_lambda_event_source_mapping.consumer.uuid
}
