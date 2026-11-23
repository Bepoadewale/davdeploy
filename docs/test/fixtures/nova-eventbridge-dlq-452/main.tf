terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.100.0"
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

variable "target_policy_rule_name" {
  type    = string
  default = "unmatched-test-rule"
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.account_id]
}

data "aws_partition" "current" {}

locals {
  prefix                  = "davdeploy-nova-eventbridge-dlq-452-nov23a1"
  bus_name                = "${local.prefix}-bus"
  rule_name               = "${local.prefix}-route"
  target_queue_name       = "${local.prefix}-target"
  consumer_dlq_name       = "${local.prefix}-consumer-dlq"
  eventbridge_dlq_name    = "${local.prefix}-eventbridge-dlq"
  target_queue_arn        = "arn:${data.aws_partition.current.partition}:sqs:${var.aws_region}:${var.account_id}:${local.target_queue_name}"
  consumer_dlq_arn        = "arn:${data.aws_partition.current.partition}:sqs:${var.aws_region}:${var.account_id}:${local.consumer_dlq_name}"
  eventbridge_dlq_arn     = "arn:${data.aws_partition.current.partition}:sqs:${var.aws_region}:${var.account_id}:${local.eventbridge_dlq_name}"
  target_queue_url        = "https://sqs.${var.aws_region}.amazonaws.com/${var.account_id}/${local.target_queue_name}"
  consumer_dlq_url        = "https://sqs.${var.aws_region}.amazonaws.com/${var.account_id}/${local.consumer_dlq_name}"
  eventbridge_dlq_url     = "https://sqs.${var.aws_region}.amazonaws.com/${var.account_id}/${local.eventbridge_dlq_name}"
  rule_arn                = "arn:${data.aws_partition.current.partition}:events:${var.aws_region}:${var.account_id}:rule/${local.bus_name}/${local.rule_name}"
  initial_target_rule_arn = "arn:${data.aws_partition.current.partition}:events:${var.aws_region}:${var.account_id}:rule/${local.bus_name}/${var.target_policy_rule_name}"
}

resource "aws_cloudwatch_event_bus" "test" {
  name = local.bus_name
}

resource "aws_cloudwatch_event_rule" "test" {
  name           = local.rule_name
  event_bus_name = aws_cloudwatch_event_bus.test.name
  event_pattern = jsonencode({
    source        = ["davdeploy.nova.test"]
    "detail-type" = ["eventbridge-dlq-test"]
  })
}

resource "aws_sqs_queue" "target" {
  name                       = local.target_queue_name
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600
  redrive_policy = jsonencode({
    deadLetterTargetArn = local.consumer_dlq_arn
    maxReceiveCount     = 5
  })
}

resource "aws_sqs_queue" "consumer_dlq" {
  name                       = local.consumer_dlq_name
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = 30
  message_retention_seconds  = 1209600
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [local.target_queue_arn]
  })
}

resource "aws_sqs_queue" "eventbridge_dlq" {
  name                       = local.eventbridge_dlq_name
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = 30
  message_retention_seconds  = 1209600
}

resource "aws_sqs_queue_policy" "target" {
  queue_url = local.target_queue_url
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowExactEventBridgeRule"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = local.target_queue_arn
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = local.initial_target_rule_arn
        }
      }
    }]
  })
}

resource "aws_sqs_queue_policy" "eventbridge_dlq" {
  queue_url = local.eventbridge_dlq_url
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowExactEventBridgeRule"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = local.eventbridge_dlq_arn
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = local.rule_arn
        }
      }
    }]
  })
}

resource "aws_cloudwatch_event_target" "test" {
  event_bus_name = aws_cloudwatch_event_bus.test.name
  rule           = aws_cloudwatch_event_rule.test.name
  target_id      = "${local.prefix}-target"
  arn            = local.target_queue_arn

  retry_policy {
    maximum_retry_attempts       = 0
    maximum_event_age_in_seconds = 60
  }

  dead_letter_config {
    arn = local.eventbridge_dlq_arn
  }

  depends_on = [
    aws_sqs_queue_policy.target,
    aws_sqs_queue_policy.eventbridge_dlq,
  ]
}
