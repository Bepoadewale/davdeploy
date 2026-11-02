locals {
  name = "davdeploy-${var.test_id}"
  tags = { ManagedBy = "terraform", Purpose = "davdeploy-module-validation", TestId = var.test_id }
}

module "queue" {
  source = "../../modules/sqs-queue"
  name   = local.name
  tags   = local.tags
}

module "events" {
  source = "../../modules/eventbridge-bus"
  name   = local.name
  tags   = local.tags
}

module "notifications" {
  source = "../../modules/sns-notifications"
  name   = local.name
  tags   = local.tags
}

resource "aws_cloudwatch_event_rule" "delivery" {
  name           = "${local.name}-delivery"
  event_bus_name = module.events.arn
  event_pattern  = jsonencode({ source = ["davdeploy.certification"] })
  tags           = local.tags
}

resource "aws_cloudwatch_event_target" "queue" {
  rule           = aws_cloudwatch_event_rule.delivery.name
  event_bus_name = module.events.arn
  arn            = module.queue.arn
}

data "aws_iam_policy_document" "queue_events" {
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [module.queue.arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.delivery.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "events" {
  queue_url = module.queue.url
  policy    = data.aws_iam_policy_document.queue_events.json
}

output "queue_url" { value = module.queue.url }
output "bus_arn" { value = module.events.arn }
output "topic_arn" { value = module.notifications.arn }
