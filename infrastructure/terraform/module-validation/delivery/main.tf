data "aws_caller_identity" "current" {}

locals {
  name = "davdeploy-${var.test_id}"
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

resource "aws_iam_role" "lambda" {
  name = "${local.name}-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "lambda_logs" {
  name = "${local.name}-logs"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:*"
    }]
  })
}

module "artifacts" {
  source = "../../modules/artifacts"
  name   = "${local.name}-${data.aws_caller_identity.current.account_id}"
  tags   = local.tags
}

module "ecr" {
  source = "../../modules/ecr"
  name   = local.name
  tags   = local.tags
}

module "lambda" {
  source     = "../../modules/lambda-service"
  name       = local.name
  role_arn   = aws_iam_role.lambda.arn
  filename   = "${path.module}/lambda.zip"
  tags       = local.tags
  depends_on = [aws_iam_role_policy.lambda_logs]
}

module "api" {
  source             = "../../modules/api-gateway-http"
  name               = local.name
  integration_uri    = module.lambda.invoke_arn
  create_integration = true
  tags               = local.tags
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowHttpApiInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${module.api.execution_arn}/*"
}

output "api_endpoint" { value = module.api.api_endpoint }
output "artifact_bucket" { value = module.artifacts.bucket_name }
output "ecr_repository" { value = module.ecr.repository_url }
