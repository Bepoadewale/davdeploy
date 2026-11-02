variable "name" { type = string }
variable "role_arn" { type = string }
variable "filename" { type = string }
variable "handler" {
  type    = string
  default = "index.handler"
}
variable "runtime" {
  type    = string
  default = "python3.12"
}
variable "tags" { type = map(string) }
variable "environment" {
  type        = map(string)
  description = "Non-secret runtime configuration. Put secrets in a managed secret store."
  default     = {}
}

resource "aws_lambda_function" "this" {
  function_name    = var.name
  role             = var.role_arn
  filename         = var.filename
  handler          = var.handler
  runtime          = var.runtime
  source_code_hash = filebase64sha256(var.filename)
  timeout          = 30
  tags             = var.tags

  dynamic "environment" {
    for_each = length(var.environment) == 0 ? [] : [var.environment]
    content {
      variables = environment.value
    }
  }
}

output "arn" { value = aws_lambda_function.this.arn }
output "invoke_arn" { value = aws_lambda_function.this.invoke_arn }
