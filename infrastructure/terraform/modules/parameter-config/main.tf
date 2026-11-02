variable "name" { type = string }
variable "value" {
  type      = string
  sensitive = true
}
variable "key_id" {
  type    = string
  default = null
}
variable "tags" { type = map(string) }

resource "aws_ssm_parameter" "this" {
  name   = var.name
  type   = "SecureString"
  value  = var.value
  key_id = var.key_id
  tags   = var.tags
}

output "arn" { value = aws_ssm_parameter.this.arn }
