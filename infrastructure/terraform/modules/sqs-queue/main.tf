variable "name" { type = string }
variable "tags" { type = map(string) }
variable "visibility_timeout_seconds" {
  type    = number
  default = 60
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  queue_arn = format(
    "arn:%s:sqs:%s:%s:%s",
    data.aws_partition.current.partition,
    data.aws_region.current.name,
    data.aws_caller_identity.current.account_id,
    var.name,
  )
  dead_letter_queue_arn = format(
    "arn:%s:sqs:%s:%s:%s-dlq",
    data.aws_partition.current.partition,
    data.aws_region.current.name,
    data.aws_caller_identity.current.account_id,
    var.name,
  )
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [local.queue_arn]
  })
  tags = var.tags
}

resource "aws_sqs_queue" "this" {
  depends_on                 = [aws_sqs_queue.dlq]
  name                       = var.name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = local.dead_letter_queue_arn
    maxReceiveCount     = 5
  })
  tags = var.tags
}

output "arn" { value = aws_sqs_queue.this.arn }
output "url" { value = aws_sqs_queue.this.url }
