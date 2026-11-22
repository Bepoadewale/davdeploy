terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.100.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  test_id    = "nov23a1"
  prefix     = "davdeploy-nova-sns-sqs-449-${local.test_id}"
  topic_name = local.prefix
  queue_name = local.prefix
  topic_arn  = "arn:${data.aws_partition.current.partition}:sns:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${local.topic_name}"
  queue_arn  = "arn:${data.aws_partition.current.partition}:sqs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${local.queue_name}"
  test_tags = {
    Product     = "davdeploy"
    Environment = "test"
    Purpose     = "nova-sns-sqs-delivery-449"
    TestRun     = local.test_id
    ManagedBy   = "Terraform"
  }
}

resource "aws_sns_topic" "delivery" {
  name = local.topic_name
  tags = local.test_tags
}

resource "aws_sqs_queue" "delivery" {
  name                      = local.queue_name
  message_retention_seconds = 3600
  sqs_managed_sse_enabled   = true
  tags                      = local.test_tags
}

resource "aws_sqs_queue_policy" "sns_publish" {
  queue_url = aws_sqs_queue.delivery.url
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowExactSnsTopic"
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = local.queue_arn
      Condition = {
        ArnEquals = { "aws:SourceArn" = local.topic_arn }
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
      }
    }]
  })
}

resource "aws_sns_topic_subscription" "delivery" {
  topic_arn            = local.topic_arn
  protocol             = "sqs"
  endpoint             = local.queue_arn
  raw_message_delivery = true
  depends_on = [
    aws_sns_topic.delivery,
    aws_sqs_queue.delivery,
    aws_sqs_queue_policy.sns_publish,
  ]
}

output "topic_arn" {
  value = aws_sns_topic.delivery.arn
}

output "queue_url" {
  value = aws_sqs_queue.delivery.url
}

output "queue_arn" {
  value = aws_sqs_queue.delivery.arn
}
