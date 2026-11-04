data "aws_caller_identity" "current" {}

locals {
  tags = {
    ManagedBy           = "davdeploy"
    DavDeployConnection = var.connection_id
    DavDeployProject    = var.project_id
    DavDeployPlan       = var.plan_digest
    Scope               = "customer-workload"
  }
  lambda_environment = var.uploads_bucket_name == "" ? {} : {
    UPLOADS_BUCKET_NAME = var.uploads_bucket_name
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

data "aws_iam_policy_document" "lambda_uploads" {
  count = var.uploads_bucket_name == "" ? 0 : 1

  statement {
    sid       = "ListConfiguredUploadBucket"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.uploads_bucket_name}"]
  }

  statement {
    sid       = "ManageConfiguredUploadObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["arn:aws:s3:::${var.uploads_bucket_name}/*"]
  }
}

resource "aws_iam_role_policy" "lambda_uploads" {
  count  = var.uploads_bucket_name == "" ? 0 : 1
  name   = "${var.service_name}-uploads"
  role   = aws_iam_role.lambda.name
  policy = data.aws_iam_policy_document.lambda_uploads[0].json
}

module "lambda" {
  source      = "../modules/lambda-service"
  name        = var.service_name
  role_arn    = aws_iam_role.lambda.arn
  filename    = var.artifact_path
  handler     = var.handler
  runtime     = var.runtime
  tags        = local.tags
  environment = local.lambda_environment
  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy.lambda_uploads,
  ]
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
