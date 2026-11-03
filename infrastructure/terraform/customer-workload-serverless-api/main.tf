data "aws_caller_identity" "current" {}

locals {
  tags = {
    ManagedBy           = "davdeploy"
    DavDeployConnection = var.connection_id
    DavDeployPlan       = var.plan_digest
    Scope               = "customer-workload"
  }
}

resource "terraform_data" "account_guard" {
  lifecycle {
    precondition {
      condition     = data.aws_caller_identity.current.account_id == var.expected_account_id
      error_message = "The assumed customer role is not in the approved AWS account."
    }
  }
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.service_name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = local.tags
  depends_on         = [terraform_data.account_guard]
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

module "lambda" {
  source     = "../modules/lambda-service"
  name       = var.service_name
  role_arn   = aws_iam_role.lambda.arn
  filename   = var.artifact_path
  handler    = var.handler
  runtime    = var.runtime
  tags       = local.tags
  depends_on = [aws_iam_role_policy_attachment.lambda_basic]
}

module "api" {
  source             = "../modules/api-gateway-http"
  name               = "${var.service_name}-http"
  integration_uri    = module.lambda.invoke_arn
  create_integration = true
  tags               = local.tags
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowHttpApiInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${module.api.execution_arn}/*/*"
}

output "api_endpoint" { value = module.api.api_endpoint }
output "lambda_arn" { value = module.lambda.arn }
