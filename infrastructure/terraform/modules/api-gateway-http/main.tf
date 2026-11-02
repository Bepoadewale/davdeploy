variable "name" { type = string }
variable "integration_uri" {
  type        = string
  description = "Optional AWS_PROXY integration URI, normally a Lambda invoke ARN."
  default     = null
}
variable "create_integration" {
  type        = bool
  description = "Create the default proxy route. Set only when integration_uri is supplied."
  default     = false
}
variable "tags" { type = map(string) }

resource "aws_apigatewayv2_api" "this" {
  name          = var.name
  protocol_type = "HTTP"
  tags          = var.tags
}

resource "aws_apigatewayv2_stage" "this" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
  tags        = var.tags
}

resource "aws_apigatewayv2_integration" "this" {
  count = var.create_integration ? 1 : 0

  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.integration_uri
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  count = var.create_integration ? 1 : 0

  api_id    = aws_apigatewayv2_api.this.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.this[0].id}"
}

output "api_endpoint" { value = aws_apigatewayv2_api.this.api_endpoint }
output "execution_arn" { value = aws_apigatewayv2_api.this.execution_arn }
