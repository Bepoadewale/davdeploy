locals {
  name = "davdeploy"
  common_tags = {
    Product     = "davdeploy"
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

resource "aws_vpc" "database" {
  cidr_block           = "10.44.0.0/20"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.common_tags, { Name = "${local.name}-database" })
}

resource "aws_subnet" "database" {
  count             = 2
  vpc_id            = aws_vpc.database.id
  cidr_block        = cidrsubnet(aws_vpc.database.cidr_block, 4, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags              = merge(local.common_tags, { Name = "${local.name}-database-${count.index + 1}" })
}

resource "aws_db_subnet_group" "control_plane" {
  name       = local.name
  subnet_ids = aws_subnet.database[*].id
  tags       = local.common_tags
}

resource "aws_security_group" "database" {
  name        = "${local.name}-database"
  description = "Aurora has no network clients; application access uses the Data API"
  vpc_id      = aws_vpc.database.id
  tags        = local.common_tags
}

resource "aws_rds_cluster" "control_plane" {
  cluster_identifier              = local.name
  engine                          = "aurora-postgresql"
  engine_mode                     = "provisioned"
  engine_version                  = var.aurora_engine_version
  database_name                   = var.database_name
  master_username                 = "davdeploy_admin"
  manage_master_user_password     = true
  enable_http_endpoint            = true
  db_subnet_group_name            = aws_db_subnet_group.control_plane.name
  vpc_security_group_ids          = [aws_security_group.database.id]
  backup_retention_period         = 7
  preferred_backup_window         = "03:00-04:00"
  storage_encrypted               = true
  deletion_protection             = var.database_deletion_protection
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${local.name}-final"
  apply_immediately               = false
  enabled_cloudwatch_logs_exports = ["postgresql"]

  serverlessv2_scaling_configuration {
    min_capacity             = var.aurora_min_capacity
    max_capacity             = var.aurora_max_capacity
    seconds_until_auto_pause = var.aurora_min_capacity == 0 ? var.aurora_seconds_until_auto_pause : null
  }

  tags = local.common_tags
}

resource "aws_rds_cluster_instance" "control_plane" {
  identifier         = "${local.name}-1"
  cluster_identifier = aws_rds_cluster.control_plane.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.control_plane.engine
  engine_version     = aws_rds_cluster.control_plane.engine_version
  tags               = local.common_tags
}

resource "aws_cognito_user_pool" "identity" {
  name                     = local.name
  user_pool_tier           = "ESSENTIALS"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "OFF"

  sign_in_policy {
    allowed_first_auth_factors = ["PASSWORD", "EMAIL_OTP"]
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  email_configuration {
    email_sending_account  = var.ses_identity_arn == "" ? "COGNITO_DEFAULT" : "DEVELOPER"
    source_arn             = var.ses_identity_arn == "" ? null : var.ses_identity_arn
    from_email_address     = var.ses_identity_arn == "" ? null : var.ses_from_address
    reply_to_email_address = var.ses_identity_arn == "" ? null : var.ses_from_address
  }

  lambda_config {
    pre_sign_up = aws_lambda_function.cognito_link.arn
  }

  deletion_protection = "ACTIVE"
  tags                = local.common_tags
}

resource "aws_cognito_user_pool_client" "frontend" {
  name         = "${local.name}-frontend"
  user_pool_id = aws_cognito_user_pool.identity.id

  generate_secret                      = false
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  read_attributes                      = ["email", "email_verified", "name"]
  supported_identity_providers         = var.google_identity_provider_enabled ? ["COGNITO", "Google"] : ["COGNITO"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = ["${var.frontend_origin}/auth/callback"]
  logout_urls                          = [var.frontend_origin]
  explicit_auth_flows                  = ["ALLOW_USER_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  access_token_validity                = 15
  id_token_validity                    = 15
  refresh_token_validity               = 7

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_cognito_user_pool_domain" "identity" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.identity.id
}

resource "aws_iam_role" "api" {
  name = "${local.name}-api"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "api_logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "api" {
  name = "control-plane-access"
  role = aws_iam_role.api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      {
        Effect   = "Allow"
        Action   = ["rds-data:BatchExecuteStatement", "rds-data:BeginTransaction", "rds-data:CommitTransaction", "rds-data:ExecuteStatement", "rds-data:RollbackTransaction"]
        Resource = aws_rds_cluster.control_plane.arn
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_rds_cluster.control_plane.master_user_secret[0].secret_arn
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.policy.arn
      },
      {
        Effect   = "Allow"
        Action   = ["sts:AssumeRole"]
        Resource = ["arn:aws:iam::*:role/davdeployDiscovery-*"]
      },
      {
        Effect   = "Allow"
        Action   = ["codebuild:BatchGetBuilds", "codebuild:StartBuild"]
        Resource = aws_codebuild_project.customer_executor.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["arn:aws:s3:::${var.customer_execution_state_bucket}/davdeploy/customer/*"]
      },
      {
        # Customer runner results are encrypted. The control-plane worker needs
        # decrypt-only access to verify the immutable result artifact; it never
        # writes customer execution artifacts.
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = var.customer_execution_kms_key_arns
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:CreateSecret", "secretsmanager:DescribeSecret", "secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"]
        Resource = ["arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:davdeploy/customer-connections/*"]
      },
      {
        Effect = "Allow"
        Action = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/amazon.nova-2-lite-v1:0",
          "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.nova_model_id}"
        ]
      }
      ],
      var.github_app_credential_secret_arn == "" ? [] : [{
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.github_app_credential_secret_arn
      }],
      var.ses_identity_arn == "" ? [] : [{
        Effect   = "Allow"
        Action   = ["ses:SendEmail"]
        Resource = var.ses_identity_arn
      }]
    )
  })
}

resource "aws_iam_role" "customer_executor" {
  name = "${local.name}-customer-executor"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "codebuild.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = merge(local.common_tags, { Purpose = "bounded-customer-terraform-execution" })
}

resource "aws_iam_role_policy" "customer_executor" {
  name = "bounded-customer-terraform-execution"
  role = aws_iam_role.customer_executor.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["arn:aws:s3:::${var.artifact_bucket}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = ["arn:aws:s3:::${var.customer_execution_state_bucket}", "arn:aws:s3:::${var.customer_execution_state_bucket}/davdeploy/customer/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:DescribeTable"]
        Resource = "arn:aws:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/${var.customer_execution_lock_table}"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:davdeploy/customer-connections/*"
      },
      {
        Effect   = "Allow"
        Action   = ["sts:AssumeRole"]
        Resource = "arn:aws:iam::*:role/davdeployExecution-*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
        Resource = var.customer_execution_kms_key_arns
      }
    ]
  })
}

resource "aws_codebuild_project" "customer_executor" {
  name           = "${local.name}-customer-executor"
  description    = "Runs only reviewed DavDeploy customer Terraform runner archives."
  service_role   = aws_iam_role.customer_executor.arn
  build_timeout  = 60
  queued_timeout = 30

  artifacts { type = "NO_ARTIFACTS" }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    privileged_mode             = true
    image_pull_credentials_type = "CODEBUILD"
  }

  source {
    type      = "NO_SOURCE"
    buildspec = <<-EOT
      version: 0.2
      phases:
        install:
          commands:
            - test -n "$DAVDEPLOY_EXECUTION_ARTIFACT_S3_URI"
            - mkdir -p /tmp/davdeploy-executor
            - aws s3 cp "$DAVDEPLOY_EXECUTION_ARTIFACT_S3_URI" /tmp/davdeploy-executor/archive.zip --only-show-errors
            - unzip -q /tmp/davdeploy-executor/archive.zip -d /tmp/davdeploy-executor/source
            - export PATH="$PATH:/usr/local/bin"
            - terraform version || (curl -fsSL -o /tmp/terraform.zip https://releases.hashicorp.com/terraform/1.14.7/terraform_1.14.7_linux_amd64.zip && unzip -q /tmp/terraform.zip -d /usr/local/bin)
        build:
          commands:
            - cd /tmp/davdeploy-executor/source
            - bash scripts/customer-workload-app-runner-pilot.sh "$DAVDEPLOY_EXECUTION_OPERATION"
    EOT
  }

  tags = merge(local.common_tags, { Purpose = "bounded-customer-terraform-execution" })
}

resource "aws_iam_role" "policy" {
  name = "${local.name}-policy"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "policy_logs" {
  role       = aws_iam_role.policy.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role" "cognito_link" {
  name = "${local.name}-cognito-link"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "cognito_link_logs" {
  role       = aws_iam_role.cognito_link.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "cognito_link" {
  name = "link-verified-google-identities"
  role = aws_iam_role.cognito_link.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["cognito-idp:ListUsers", "cognito-idp:AdminLinkProviderForUser"]
      Resource = aws_cognito_user_pool.identity.arn
    }]
  })
}

locals {
  lambda_log_groups = toset(["api", "cognito-link", "migrate", "policy", "worker"])
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = local.lambda_log_groups
  name              = "/aws/lambda/${local.name}-${each.value}"
  retention_in_days = 14
  tags              = local.common_tags
}

import {
  for_each = toset(["api", "cognito-link", "migrate", "worker"])
  to       = aws_cloudwatch_log_group.lambda[each.value]
  id       = "/aws/lambda/${local.name}-${each.value}"
}

resource "aws_lambda_function" "policy" {
  function_name     = "${local.name}-policy"
  role              = aws_iam_role.policy.arn
  runtime           = "python3.12"
  handler           = "davdeploy.lambda_policy.handler"
  s3_bucket         = var.artifact_bucket
  s3_key            = var.artifact_key
  s3_object_version = var.artifact_object_version
  timeout           = 5
  memory_size       = 256
  tags              = local.common_tags
  depends_on        = [aws_cloudwatch_log_group.lambda]
}

resource "aws_lambda_function" "cognito_link" {
  function_name     = "${local.name}-cognito-link"
  role              = aws_iam_role.cognito_link.arn
  runtime           = "python3.12"
  handler           = "davdeploy.lambda_cognito_link.handler"
  s3_bucket         = var.artifact_bucket
  s3_key            = var.artifact_key
  s3_object_version = var.artifact_object_version
  timeout           = 10
  memory_size       = 256
  tags              = local.common_tags
  depends_on        = [aws_cloudwatch_log_group.lambda]
}

resource "aws_lambda_permission" "cognito_link" {
  statement_id  = "AllowCognito"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cognito_link.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.identity.arn
}

locals {
  runtime_environment = {
    DAVDEPLOY_HOSTED_MODE                        = "true"
    DAVDEPLOY_AUTO_MIGRATE                       = "false"
    DAVDEPLOY_AURORA_CLUSTER_ARN                 = aws_rds_cluster.control_plane.arn
    DAVDEPLOY_DATABASE_SECRET_ARN                = aws_rds_cluster.control_plane.master_user_secret[0].secret_arn
    DAVDEPLOY_DATABASE_NAME                      = var.database_name
    DAVDEPLOY_ALLOWED_FRONTEND_ORIGINS           = var.frontend_origin
    DAVDEPLOY_JWKS_URL                           = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.identity.id}/.well-known/jwks.json"
    DAVDEPLOY_OIDC_ISSUER                        = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.identity.id}"
    DAVDEPLOY_OIDC_AUDIENCE                      = aws_cognito_user_pool_client.frontend.id
    DAVDEPLOY_POLICY_FUNCTION_ARN                = aws_lambda_function.policy.arn
    DAVDEPLOY_MODEL_PROVIDER                     = "bedrock"
    DAVDEPLOY_BEDROCK_MODEL_ID                   = var.nova_model_id
    DAVDEPLOY_EXECUTOR_MODE                      = "embedded_fixture"
    DAVDEPLOY_EMAIL_PROVIDER                     = var.ses_identity_arn == "" ? "disabled" : "ses"
    DAVDEPLOY_SES_FROM_ADDRESS                   = var.ses_from_address
    DAVDEPLOY_FRONTEND_ORIGIN                    = var.frontend_origin
    DAVDEPLOY_CONNECTION_SECRET_BACKEND          = "aws_secrets_manager"
    DAVDEPLOY_CONNECTION_SECRET_PREFIX           = "davdeploy/customer-connections"
    DAVDEPLOY_AWS_LIVE_DISCOVERY_ENABLED         = "true"
    DAVDEPLOY_DISCOVERY_BROKER_ROLE_ARN          = aws_iam_role.api.arn
    DAVDEPLOY_EXECUTION_BROKER_ROLE_ARN          = aws_iam_role.customer_executor.arn
    DAVDEPLOY_AWS_CONNECTION_TEMPLATE_URL        = var.aws_connection_template_url
    DAVDEPLOY_CUSTOMER_EXECUTOR_PROJECT          = aws_codebuild_project.customer_executor.name
    DAVDEPLOY_CLOUD_EXECUTION_BACKEND            = "codebuild"
    DAVDEPLOY_CLOUD_EXECUTION_COMMAND_ENABLED    = tostring(var.enable_customer_cloud_execution)
    DAVDEPLOY_ENABLE_APP_RUNNER_EXECUTION        = tostring(var.enable_customer_cloud_execution)
    ALLOW_CLOUD_PLAN                             = tostring(var.enable_customer_cloud_execution)
    ALLOW_CLOUD_APPLY                            = tostring(var.enable_customer_cloud_execution)
    DAVDEPLOY_CUSTOMER_EXECUTION_ARTIFACT_S3_URI = "s3://${var.artifact_bucket}/${var.customer_execution_artifact_key}"
    DAVDEPLOY_CUSTOMER_EXECUTION_STATE_BUCKET    = var.customer_execution_state_bucket
    DAVDEPLOY_CUSTOMER_EXECUTION_LOCK_TABLE      = var.customer_execution_lock_table
    DAVDEPLOY_WORKER_QUEUE_URL                   = aws_sqs_queue.worker.id
    DAVDEPLOY_GITHUB_APP_READ_ONLY               = tostring(var.enable_github_app_read_only)
    DAVDEPLOY_GITHUB_APP_ID                      = var.github_app_id
    DAVDEPLOY_GITHUB_APP_INSTALLATION_ID         = var.github_app_installation_id
    DAVDEPLOY_GITHUB_APP_CREDENTIAL_SECRET_ARN   = var.github_app_credential_secret_arn
  }
}

resource "aws_lambda_function" "api" {
  function_name     = "${local.name}-api"
  role              = aws_iam_role.api.arn
  runtime           = "python3.12"
  handler           = "davdeploy.lambda_api.handler"
  s3_bucket         = var.artifact_bucket
  s3_key            = var.artifact_key
  s3_object_version = var.artifact_object_version
  timeout           = 29
  memory_size       = 1024
  depends_on        = [aws_cloudwatch_log_group.lambda]

  environment {
    variables = local.runtime_environment
  }
  tags = local.common_tags
}

resource "aws_lambda_function" "migrate" {
  function_name     = "${local.name}-migrate"
  role              = aws_iam_role.api.arn
  runtime           = "python3.12"
  handler           = "davdeploy.lambda_migrate.handler"
  s3_bucket         = var.artifact_bucket
  s3_key            = var.artifact_key
  s3_object_version = var.artifact_object_version
  timeout           = 300
  memory_size       = 1024
  depends_on        = [aws_cloudwatch_log_group.lambda]

  environment {
    variables = local.runtime_environment
  }
  tags = local.common_tags
}

data "aws_iam_role" "terraform_apply" {
  name = "davdeploy-terraform-apply-github"
}

resource "aws_iam_role_policy" "terraform_apply_migrations" {
  name = "invoke-davdeploy-release-migrations"
  role = data.aws_iam_role.terraform_apply.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = aws_lambda_function.migrate.arn
    }]
  })
}

resource "aws_apigatewayv2_api" "control_plane" {
  name          = local.name
  protocol_type = "HTTP"

  cors_configuration {
    allow_credentials = false
    allow_headers     = ["Authorization", "Content-Type", "Idempotency-Key"]
    allow_methods     = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_origins     = [var.frontend_origin]
    expose_headers    = ["X-davdeploy-API-Version", "X-Request-ID", "X-Correlation-ID"]
    max_age           = 600
  }
  tags = local.common_tags
}

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.control_plane.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.frontend.id]
    issuer   = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.identity.id}"
  }
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.control_plane.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

resource "aws_apigatewayv2_route" "authenticated" {
  api_id             = aws_apigatewayv2_api.control_plane.id
  route_key          = "$default"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.control_plane.id
  route_key = "GET /healthz"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

# An authenticated $default route also captures preflight requests. Explicit OPTIONS routes take
# precedence and let the API's CORS middleware answer browsers without weakening application routes.
resource "aws_apigatewayv2_route" "preflight_root" {
  api_id    = aws_apigatewayv2_api.control_plane.id
  route_key = "OPTIONS /"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

resource "aws_apigatewayv2_route" "preflight_proxy" {
  api_id    = aws_apigatewayv2_api.control_plane.id
  route_key = "OPTIONS /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.control_plane.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 50
    throttling_rate_limit  = 25
  }
  tags = local.common_tags
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.control_plane.execution_arn}/*/*"
}

resource "aws_sqs_queue" "worker_dead_letter" {
  name                      = "${local.name}-worker-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = local.common_tags
}

resource "aws_sqs_queue" "worker" {
  name                       = "${local.name}-worker"
  visibility_timeout_seconds = 360
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.worker_dead_letter.arn
    maxReceiveCount     = 5
  })
  tags = local.common_tags
}

resource "aws_sqs_queue_policy" "worker_events" {
  queue_url = aws_sqs_queue.worker.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.worker.arn
    }]
  })
}

resource "aws_cloudwatch_event_rule" "customer_executor_completion" {
  name = "${local.name}-customer-executor-completion"
  event_pattern = jsonencode({
    source        = ["aws.codebuild"]
    "detail-type" = ["CodeBuild Build State Change"]
    detail        = { "project-name" = [aws_codebuild_project.customer_executor.name] }
  })
  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "customer_executor_completion" {
  rule       = aws_cloudwatch_event_rule.customer_executor_completion.name
  arn        = aws_sqs_queue.worker.arn
  depends_on = [aws_sqs_queue_policy.worker_events]
}

resource "aws_iam_role_policy" "worker_queue" {
  name = "worker-queue"
  role = aws_iam_role.api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
      Resource = aws_sqs_queue.worker.arn
    }]
  })
}

resource "aws_lambda_function" "worker" {
  function_name     = "${local.name}-worker"
  role              = aws_iam_role.api.arn
  runtime           = "python3.12"
  handler           = "davdeploy.lambda_worker.handler"
  s3_bucket         = var.artifact_bucket
  s3_key            = var.artifact_key
  s3_object_version = var.artifact_object_version
  timeout           = 300
  memory_size       = 1024
  depends_on        = [aws_cloudwatch_log_group.lambda]

  environment {
    variables = local.runtime_environment
  }
  tags = local.common_tags
}

resource "aws_lambda_event_source_mapping" "worker" {
  event_source_arn = aws_sqs_queue.worker.arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 1

  depends_on = [aws_iam_role_policy.worker_queue]
}

resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = var.budget_notification_email == "" ? [] : [var.budget_notification_email]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = 80
      threshold_type             = "PERCENTAGE"
      notification_type          = "FORECASTED"
      subscriber_email_addresses = [notification.value]
    }
  }
}

resource "aws_sns_topic" "operations" {
  name = "${local.name}-operations"
  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "operations_email" {
  count     = var.budget_notification_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.operations.arn
  protocol  = "email"
  endpoint  = var.budget_notification_email
}

locals {
  alarm_actions = [aws_sns_topic.operations.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "${local.name}-api-errors"
  alarm_description   = "The control-plane API reported a Lambda error."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  dimensions          = { FunctionName = aws_lambda_function.api.function_name }
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "worker_errors" {
  alarm_name          = "${local.name}-worker-errors"
  alarm_description   = "The durable worker reported a Lambda error."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  dimensions          = { FunctionName = aws_lambda_function.worker.function_name }
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx" {
  alarm_name          = "${local.name}-api-gateway-5xx"
  alarm_description   = "The public API returned a server error."
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  dimensions = {
    ApiId = aws_apigatewayv2_api.control_plane.id
    Stage = aws_apigatewayv2_stage.default.name
  }
  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "worker_dead_letter" {
  alarm_name          = "${local.name}-worker-dead-letter"
  alarm_description   = "At least one worker job reached the dead-letter queue."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  dimensions          = { QueueName = aws_sqs_queue.worker_dead_letter.name }
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "database_capacity_high" {
  alarm_name          = "${local.name}-database-capacity-high"
  alarm_description   = "Aurora stayed near the configured serverless capacity ceiling."
  namespace           = "AWS/RDS"
  metric_name         = "ServerlessDatabaseCapacity"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = var.aurora_max_capacity * 0.8
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  dimensions          = { DBClusterIdentifier = aws_rds_cluster.control_plane.cluster_identifier }
  tags                = local.common_tags
}

check "no_network_egress_infrastructure" {
  assert {
    condition     = length(aws_subnet.database) == 2
    error_message = "Aurora requires exactly two isolated subnets. This stack must not add NAT or Internet Gateways."
  }
}
