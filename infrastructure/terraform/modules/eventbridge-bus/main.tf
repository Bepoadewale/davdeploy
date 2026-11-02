variable "name" { type = string }
variable "tags" { type = map(string) }

resource "aws_cloudwatch_event_bus" "this" {
  name = var.name
  tags = var.tags
}

output "arn" { value = aws_cloudwatch_event_bus.this.arn }
