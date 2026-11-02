variable "name" { type = string }
variable "role_arn" { type = string }
variable "definition" {
  type        = string
  description = "Amazon States Language JSON. The caller owns resource permissions."
}
variable "tags" { type = map(string) }

resource "aws_sfn_state_machine" "this" {
  name       = var.name
  role_arn   = var.role_arn
  definition = var.definition
  type       = "STANDARD"
  tags       = var.tags
}

output "arn" { value = aws_sfn_state_machine.this.arn }
