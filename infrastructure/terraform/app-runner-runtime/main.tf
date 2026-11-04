data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name = "davdeploy-runtime"
  tags = {
    Project         = "davdeploy"
    ManagedBy       = "terraform"
    Scope           = "platform"
    Placement       = "platform"
    AccountBoundary = "same-account-pilot"
    Cell            = "platform-1"
    Purpose         = "davdeploy-control-plane"
  }
  secret_prefix       = trim(var.connection_secret_prefix, "/")
  database_secret_arn = var.enable_durable_database ? aws_db_instance.control_plane[0].master_user_secret[0].secret_arn : ""
  runtime_env_common = {
    DAVDEPLOY_POLICY_FIXTURE              = "false"
    DAVDEPLOY_AWS_LIVE_DISCOVERY_ENABLED  = "true"
    DAVDEPLOY_AWS_VERIFY_INLINE           = "true"
    DAVDEPLOY_CONNECTION_SECRET_BACKEND   = "aws_secrets_manager"
    DAVDEPLOY_CONNECTION_SECRET_PREFIX    = local.secret_prefix
    DAVDEPLOY_AWS_CONNECTION_TEMPLATE_URL = var.customer_template_url
    AWS_DEFAULT_REGION                    = var.region
    AWS_REGION                            = var.region
  }
  runtime_env_database = var.enable_durable_database ? {
    DAVDEPLOY_HOSTED_MODE         = "true"
    DAVDEPLOY_DATABASE_SECRET_ARN = local.database_secret_arn
    DAVDEPLOY_DATABASE_NAME       = var.database_name
    } : {
    DAVDEPLOY_HOSTED_MODE  = "false"
    DAVDEPLOY_DATABASE_URL = "sqlite+pysqlite:////tmp/davdeploy.db"
  }
  runtime_env_model = var.enable_nova_model ? {
    DAVDEPLOY_MODEL_PROVIDER          = "bedrock"
    DAVDEPLOY_MODEL_FALLBACK          = "disabled"
    DAVDEPLOY_BEDROCK_REGION          = var.region
    DAVDEPLOY_BEDROCK_MODEL_ID        = var.nova_model_id
    DAVDEPLOY_MODEL_DATA_POLICY       = "bedrock-no-training"
    DAVDEPLOY_MODEL_MAX_OUTPUT_TOKENS = "2000"
    DAVDEPLOY_MODEL_TIMEOUT_SECONDS   = "60"
    } : {
    DAVDEPLOY_MODEL_PROVIDER = "fixture"
  }
  runtime_env_identity = var.enable_service ? {
    DAVDEPLOY_JWKS_URL                 = var.oidc_jwks_url
    DAVDEPLOY_OIDC_ISSUER              = var.oidc_issuer
    DAVDEPLOY_OIDC_AUDIENCE            = var.oidc_audience
    DAVDEPLOY_OPA_URL                  = var.policy_url
    DAVDEPLOY_ALLOWED_FRONTEND_ORIGINS = var.frontend_origin
  } : {}
  runtime_env_local_signing = var.enable_durable_database ? {} : {
    DAVDEPLOY_LOCAL_SIGNING_KEY_SECRET_ARN = aws_secretsmanager_secret.runtime_signing_key[0].arn
  }
  runtime_env = merge(
    local.runtime_env_common,
    local.runtime_env_database,
    local.runtime_env_model,
    local.runtime_env_identity,
    local.runtime_env_local_signing,
  )
  azs                     = slice(data.aws_availability_zones.available.names, 0, 2)
  service_network_enabled = var.enable_durable_database && var.enable_service
}

resource "terraform_data" "runtime_guard" {
  lifecycle {
    precondition {
      condition     = !var.enable_service || var.enable_durable_database
      error_message = "Hosted App Runner service activation requires the durable PostgreSQL database."
    }
    precondition {
      condition = !var.enable_service || (
        can(regex("^https://", var.oidc_jwks_url)) &&
        can(regex("^https://", var.oidc_issuer)) &&
        length(trimspace(var.oidc_audience)) > 0 &&
        can(regex("^https://", var.policy_url))
      )
      error_message = "Hosted service activation requires HTTPS JWKS, issuer and policy URLs plus an exact OIDC audience."
    }
    precondition {
      condition = !var.enable_service || (
        can(regex("^https://[^/]+$", var.frontend_origin)) &&
        !strcontains(var.frontend_origin, "*")
      )
      error_message = "Hosted service activation requires one exact HTTPS frontend origin without a path or wildcard."
    }
    precondition {
      condition     = !var.enable_service || var.image_identifier != "placeholder.invalid/davdeploy:unset"
      error_message = "Hosted service activation requires an immutable ECR image identifier."
    }
  }
}

resource "random_password" "runtime_signing_key" {
  count   = var.enable_durable_database ? 0 : 1
  length  = 48
  special = false
}

resource "aws_secretsmanager_secret" "runtime_signing_key" {
  count                   = var.enable_durable_database ? 0 : 1
  name                    = "davdeploy/runtime/local-signing-key"
  description             = "Temporary fixture signing key for the hosted davdeploy verification runtime."
  recovery_window_in_days = 0
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "runtime_signing_key" {
  count         = var.enable_durable_database ? 0 : 1
  secret_id     = aws_secretsmanager_secret.runtime_signing_key[0].id
  secret_string = random_password.runtime_signing_key[0].result
}

resource "aws_ecr_repository" "runtime" {
  name                 = local.name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = local.tags
}

data "aws_iam_policy_document" "apprunner_ecr_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["build.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "apprunner_ecr_access" {
  name                 = "davdeploy-apprunner-ecr-access"
  description          = "Allows App Runner to pull the davdeploy runtime image from ECR."
  assume_role_policy   = data.aws_iam_policy_document.apprunner_ecr_trust.json
  max_session_duration = 3600
  tags                 = local.tags
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr_access" {
  role       = aws_iam_role.apprunner_ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

data "aws_iam_policy_document" "runtime_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "runtime" {
  name                 = "davdeploy-control-plane-runtime"
  description          = "AWS-hosted davdeploy runtime identity for read-only customer AWS verification."
  assume_role_policy   = data.aws_iam_policy_document.runtime_trust.json
  max_session_duration = 3600
  tags                 = local.tags
}

data "aws_iam_policy_document" "runtime_permissions" {
  statement {
    sid       = "AssumeOnlyCustomerReadOnlyDiscoveryRoles"
    effect    = "Allow"
    actions   = ["sts:AssumeRole"]
    resources = ["arn:aws:iam::*:role/davdeployDiscovery-*"]
  }

  statement {
    sid    = "ManageConnectionExternalIds"
    effect = "Allow"
    actions = [
      "secretsmanager:CreateSecret",
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetSecretValue",
      "secretsmanager:PutSecretValue",
      "secretsmanager:TagResource",
    ]
    resources = [
      "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${local.secret_prefix}/*"
    ]
  }

  dynamic "statement" {
    for_each = var.enable_durable_database ? [] : [aws_secretsmanager_secret.runtime_signing_key[0].arn]
    content {
      sid       = "ReadRuntimeFixtureSigningKey"
      effect    = "Allow"
      actions   = ["secretsmanager:DescribeSecret", "secretsmanager:GetSecretValue"]
      resources = [statement.value]
    }
  }

  dynamic "statement" {
    for_each = var.enable_durable_database ? [local.database_secret_arn] : []
    content {
      sid       = "ReadControlPlaneDatabaseSecret"
      effect    = "Allow"
      actions   = ["secretsmanager:DescribeSecret", "secretsmanager:GetSecretValue"]
      resources = [statement.value]
    }
  }

  dynamic "statement" {
    for_each = var.enable_nova_model ? [1] : []
    content {
      sid       = "InvokeNova2LiteInferenceProfile"
      effect    = "Allow"
      actions   = ["bedrock:InvokeModel"]
      resources = ["arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.nova_model_id}"]
    }
  }

  dynamic "statement" {
    for_each = var.enable_nova_model ? [1] : []
    content {
      sid       = "InvokeNova2LiteOnlyThroughProfile"
      effect    = "Allow"
      actions   = ["bedrock:InvokeModel"]
      resources = ["arn:aws:bedrock:*::foundation-model/amazon.nova-2-lite-v1:0"]
      condition {
        test     = "StringEquals"
        variable = "bedrock:InferenceProfileArn"
        values   = ["arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.nova_model_id}"]
      }
    }
  }
}

resource "aws_iam_role_policy" "runtime_permissions" {
  name   = "davdeploy-runtime-customer-discovery"
  role   = aws_iam_role.runtime.id
  policy = data.aws_iam_policy_document.runtime_permissions.json
}

resource "aws_cloudwatch_log_group" "runtime" {
  name              = "/aws/apprunner/${local.name}"
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_sns_topic" "platform_alerts" {
  name              = "davdeploy-platform-alerts"
  kms_master_key_id = "alias/aws/sns"
  tags              = local.tags
}

resource "aws_sns_topic_subscription" "platform_alert_email" {
  count     = var.monitoring_notification_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.platform_alerts.arn
  protocol  = "email"
  endpoint  = var.monitoring_notification_email
}

resource "aws_budgets_budget" "platform" {
  name         = "davdeploy-platform-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_platform_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = ["user:Project$davdeploy"]
  }

  dynamic "notification" {
    for_each = var.monitoring_notification_email == "" ? [] : [50, 80, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.monitoring_notification_email]
    }
  }

  dynamic "notification" {
    for_each = var.monitoring_notification_email == "" ? [] : [100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "FORECASTED"
      subscriber_email_addresses = [var.monitoring_notification_email]
    }
  }

  tags = local.tags
}

resource "aws_vpc" "runtime" {
  count                = var.enable_durable_database ? 1 : 0
  cidr_block           = var.runtime_vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(local.tags, { Name = "${local.name}-vpc" })
}

resource "aws_internet_gateway" "runtime" {
  count  = local.service_network_enabled ? 1 : 0
  vpc_id = aws_vpc.runtime[0].id
  tags   = merge(local.tags, { Name = "${local.name}-igw" })
}

resource "aws_subnet" "public" {
  count                   = local.service_network_enabled ? 2 : 0
  vpc_id                  = aws_vpc.runtime[0].id
  cidr_block              = cidrsubnet(var.runtime_vpc_cidr, 8, count.index)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true
  tags                    = merge(local.tags, { Name = "${local.name}-public-${count.index + 1}" })
}

resource "aws_subnet" "private" {
  count             = var.enable_durable_database ? 2 : 0
  vpc_id            = aws_vpc.runtime[0].id
  cidr_block        = cidrsubnet(var.runtime_vpc_cidr, 8, count.index + 10)
  availability_zone = local.azs[count.index]
  tags              = merge(local.tags, { Name = "${local.name}-private-${count.index + 1}" })
}

resource "aws_eip" "nat" {
  count  = local.service_network_enabled ? 1 : 0
  domain = "vpc"
  tags   = merge(local.tags, { Name = "${local.name}-nat" })
}

resource "aws_nat_gateway" "runtime" {
  count         = local.service_network_enabled ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id
  tags          = merge(local.tags, { Name = "${local.name}-nat" })
  depends_on    = [aws_internet_gateway.runtime]
}

resource "aws_route_table" "public" {
  count  = local.service_network_enabled ? 1 : 0
  vpc_id = aws_vpc.runtime[0].id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.runtime[0].id
  }
  tags = merge(local.tags, { Name = "${local.name}-public" })
}

resource "aws_route_table_association" "public" {
  count          = local.service_network_enabled ? 2 : 0
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_route_table" "private" {
  count  = local.service_network_enabled ? 1 : 0
  vpc_id = aws_vpc.runtime[0].id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.runtime[0].id
  }
  tags = merge(local.tags, { Name = "${local.name}-private" })
}

resource "aws_route_table_association" "private" {
  count          = local.service_network_enabled ? 2 : 0
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[0].id
}

resource "aws_security_group" "runtime" {
  count       = var.enable_durable_database ? 1 : 0
  name        = "${local.name}-app-runner"
  description = "App Runner VPC connector egress for davdeploy hosted runtime."
  vpc_id      = aws_vpc.runtime[0].id

  egress {
    description = "Allow runtime egress through private subnets for AWS APIs and approved integrations."
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${local.name}-app-runner" })
}

resource "aws_security_group" "database" {
  count       = var.enable_durable_database ? 1 : 0
  name        = "${local.name}-database"
  description = "Private PostgreSQL access from davdeploy App Runner only."
  vpc_id      = aws_vpc.runtime[0].id

  ingress {
    description     = "PostgreSQL from davdeploy runtime."
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.runtime[0].id]
  }

  tags = merge(local.tags, { Name = "${local.name}-database" })
}

resource "aws_db_subnet_group" "control_plane" {
  count      = var.enable_durable_database ? 1 : 0
  name       = "${local.name}-database"
  subnet_ids = aws_subnet.private[*].id
  tags       = local.tags
}

resource "aws_db_instance" "control_plane" {
  count                       = var.enable_durable_database ? 1 : 0
  identifier                  = "${local.name}-postgres"
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = var.database_instance_class
  allocated_storage           = var.database_allocated_storage
  db_name                     = var.database_name
  username                    = "davdeploy"
  manage_master_user_password = true
  publicly_accessible         = false
  skip_final_snapshot         = false
  final_snapshot_identifier   = "${local.name}-postgres-final"
  deletion_protection         = var.database_deletion_protection
  db_subnet_group_name        = aws_db_subnet_group.control_plane[0].name
  vpc_security_group_ids      = [aws_security_group.database[0].id]
  storage_encrypted           = true
  storage_type                = "gp3"
  backup_retention_period     = var.database_backup_retention_days
  backup_window               = "03:00-04:00"
  maintenance_window          = "sun:04:30-sun:05:30"
  auto_minor_version_upgrade  = true
  copy_tags_to_snapshot       = true
  delete_automated_backups    = false
  tags                        = local.tags
}

resource "aws_apprunner_vpc_connector" "runtime" {
  count              = local.service_network_enabled ? 1 : 0
  vpc_connector_name = "${local.name}-database"
  subnets            = aws_subnet.private[*].id
  security_groups    = [aws_security_group.runtime[0].id]
  tags               = local.tags
}

resource "aws_cloudwatch_metric_alarm" "database_cpu_high" {
  count               = var.enable_durable_database ? 1 : 0
  alarm_name          = "davdeploy-platform-rds-cpu-high"
  alarm_description   = "davdeploy platform PostgreSQL CPU exceeded 80 percent for 15 minutes."
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.platform_alerts.arn]
  ok_actions          = [aws_sns_topic.platform_alerts.arn]
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.control_plane[0].identifier
  }
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "database_storage_low" {
  count               = var.enable_durable_database ? 1 : 0
  alarm_name          = "davdeploy-platform-rds-storage-low"
  alarm_description   = "davdeploy platform PostgreSQL has less than 2 GiB free storage."
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 2147483648
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.platform_alerts.arn]
  ok_actions          = [aws_sns_topic.platform_alerts.arn]
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.control_plane[0].identifier
  }
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "database_connections_high" {
  count               = var.enable_durable_database ? 1 : 0
  alarm_name          = "davdeploy-platform-rds-connections-high"
  alarm_description   = "davdeploy platform PostgreSQL connection count exceeded the pilot threshold."
  namespace           = "AWS/RDS"
  metric_name         = "DatabaseConnections"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 60
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.platform_alerts.arn]
  ok_actions          = [aws_sns_topic.platform_alerts.arn]
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.control_plane[0].identifier
  }
  tags = local.tags
}

resource "aws_apprunner_service" "runtime" {
  count        = var.enable_service ? 1 : 0
  service_name = local.name
  tags         = local.tags

  source_configuration {
    auto_deployments_enabled = false

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr_access.arn
    }

    image_repository {
      image_identifier      = var.image_identifier
      image_repository_type = "ECR"

      image_configuration {
        port = "8080"
        runtime_environment_variables = merge(local.runtime_env, {
          DAVDEPLOY_CONTROL_PLANE_ROLE_ARN = aws_iam_role.runtime.arn
        })
      }
    }
  }

  instance_configuration {
    cpu               = var.cpu
    memory            = var.memory
    instance_role_arn = aws_iam_role.runtime.arn
  }

  dynamic "network_configuration" {
    for_each = local.service_network_enabled ? [1] : []
    content {
      egress_configuration {
        egress_type       = "VPC"
        vpc_connector_arn = aws_apprunner_vpc_connector.runtime[0].arn
      }
    }
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/healthz"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  depends_on = [
    aws_cloudwatch_log_group.runtime,
    aws_iam_role_policy.runtime_permissions,
    aws_iam_role_policy_attachment.apprunner_ecr_access,
    aws_secretsmanager_secret_version.runtime_signing_key,
    aws_db_instance.control_plane,
    terraform_data.runtime_guard,
  ]
}

resource "aws_cloudwatch_metric_alarm" "service_5xx" {
  count               = var.enable_service ? 1 : 0
  alarm_name          = "davdeploy-platform-apprunner-5xx"
  alarm_description   = "davdeploy App Runner returned five or more 5xx responses in five minutes."
  namespace           = "AWS/AppRunner"
  metric_name         = "5xxStatusResponses"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.platform_alerts.arn]
  ok_actions          = [aws_sns_topic.platform_alerts.arn]
  dimensions = {
    ServiceName = aws_apprunner_service.runtime[0].service_name
    ServiceID   = aws_apprunner_service.runtime[0].service_id
  }
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "service_latency" {
  count               = var.enable_service ? 1 : 0
  alarm_name          = "davdeploy-platform-apprunner-latency"
  alarm_description   = "davdeploy App Runner p95 latency exceeded two seconds for ten minutes."
  namespace           = "AWS/AppRunner"
  metric_name         = "RequestLatency"
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 2
  threshold           = 2000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.platform_alerts.arn]
  ok_actions          = [aws_sns_topic.platform_alerts.arn]
  dimensions = {
    ServiceName = aws_apprunner_service.runtime[0].service_name
    ServiceID   = aws_apprunner_service.runtime[0].service_id
  }
  tags = local.tags
}
