locals {
  function_name = "davdeploy-nova-lambda-489-${var.run_id}"
  log_group     = "/aws/lambda/${local.function_name}"
  handler_name  = "handler_${var.handler_version}.handler"
  archive_path  = "/tmp/${local.function_name}-${var.handler_version}.zip"

  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-nova-lambda-module-test"
    TestId    = "nova-lambda-service-489-${var.run_id}"
  }
}

data "archive_file" "function" {
  type        = "zip"
  source_file = "${path.module}/handler_${var.handler_version}.py"
  output_path = local.archive_path
}

resource "aws_iam_role" "function" {
  name = "${local.function_name}-execution"

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

resource "aws_cloudwatch_log_group" "function" {
  name              = local.log_group
  retention_in_days = 1
  tags              = local.tags
}

resource "aws_iam_role_policy" "logs" {
  name = "${local.function_name}-logs"
  role = aws_iam_role.function.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:${local.log_group}:*"
    }]
  })

  depends_on = [aws_cloudwatch_log_group.function]
}

module "lambda_service" {
  source      = "../../../../infrastructure/terraform/modules/lambda-service"
  name        = local.function_name
  role_arn    = aws_iam_role.function.arn
  filename    = data.archive_file.function.output_path
  handler     = local.handler_name
  runtime     = "python3.12"
  tags        = local.tags
  environment = { TEST_ID = "nova-lambda-service-489-${var.run_id}" }

  depends_on = [aws_iam_role_policy.logs]
}
