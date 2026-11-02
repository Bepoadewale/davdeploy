variable "name" { type = string }
variable "tags" { type = map(string) }
variable "subscriptions" {
  type = list(object({
    protocol = string
    endpoint = string
  }))
  default = []
}

resource "aws_sns_topic" "this" {
  name              = var.name
  kms_master_key_id = "alias/aws/sns"
  tags              = var.tags
}

resource "aws_sns_topic_subscription" "this" {
  for_each  = { for subscription in var.subscriptions : "${subscription.protocol}:${subscription.endpoint}" => subscription }
  topic_arn = aws_sns_topic.this.arn
  protocol  = each.value.protocol
  endpoint  = each.value.endpoint
}

output "arn" { value = aws_sns_topic.this.arn }
