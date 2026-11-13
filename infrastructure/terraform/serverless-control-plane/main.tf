locals {
  name = "davdeploy"
  common_tags = {
    Product     = "davdeploy"
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}

locals {
  nova_plan_only_project_name                = "${local.name}-nova-plan-only"
  nova_plan_only_input_key                   = "plans/nova-generated/requests/*/input.json"
  nova_plan_only_build_prefix                = "plans/nova-generated/builds/*"
  nova_plan_only_scoped_prefix               = "plans/nova-generated/builds/$${codebuild:buildArn}"
  nova_plan_only_build_input_key             = "${local.nova_plan_only_build_prefix}/input.json"
  nova_plan_only_build_result_key            = "${local.nova_plan_only_build_prefix}/result.json"
  nova_plan_only_build_saved_plan_key        = "${local.nova_plan_only_build_prefix}/org-????????????????????????????????/project-????????????????????????????????/revision-????????????????????????????????/*.tfplan"
  nova_plan_only_build_workspace_key         = "${local.nova_plan_only_build_prefix}/org-????????????????????????????????/project-????????????????????????????????/revision-????????????????????????????????/*.workspace.tar.gz"
  nova_plan_only_scoped_input_key            = "${local.nova_plan_only_scoped_prefix}/input.json"
  nova_plan_only_scoped_result_key           = "${local.nova_plan_only_scoped_prefix}/result.json"
  nova_plan_only_scoped_saved_plan_key       = "${local.nova_plan_only_scoped_prefix}/org-*/project-*/revision-*/*.tfplan"
  nova_plan_only_scoped_workspace_key        = "${local.nova_plan_only_scoped_prefix}/org-*/project-*/revision-*/*.workspace.tar.gz"
  nova_exact_plan_apply_project_name         = "${local.name}-nova-saved-plan-apply"
  nova_exact_plan_apply_input_key            = "plans/nova-generated/apply-requests/*/input.json"
  nova_exact_plan_apply_build_prefix         = "plans/nova-generated/apply-builds/*"
  nova_exact_plan_apply_build_scoped_prefix  = "plans/nova-generated/apply-builds/$${codebuild:buildArn}"
  nova_exact_plan_apply_build_input_key      = "${local.nova_exact_plan_apply_build_prefix}/input.json"
  nova_exact_plan_apply_build_result_key     = "${local.nova_exact_plan_apply_build_prefix}/result.json"
  nova_exact_plan_apply_scoped_input_key     = "${local.nova_exact_plan_apply_build_scoped_prefix}/input.json"
  nova_exact_plan_apply_scoped_result_key    = "${local.nova_exact_plan_apply_build_scoped_prefix}/result.json"
  nova_exact_plan_apply_plan_key             = "plans/nova-generated/builds/*/org-????????????????????????????????/project-????????????????????????????????/revision-????????????????????????????????/*.tfplan"
  nova_exact_plan_apply_workspace_key        = "plans/nova-generated/builds/*/org-????????????????????????????????/project-????????????????????????????????/revision-????????????????????????????????/*.workspace.tar.gz"
  nova_exact_plan_apply_scoped_plan_key      = "plans/nova-generated/builds/*/org-*/project-*/revision-*/*.tfplan"
  nova_exact_plan_apply_scoped_workspace_key = "plans/nova-generated/builds/*/org-*/project-*/revision-*/*.workspace.tar.gz"
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

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
  # Cognito requires a password first factor before software-token MFA.
  mfa_configuration = "ON"

  software_token_mfa_configuration {
    enabled = true
  }

  sign_in_policy {
    allowed_first_auth_factors = ["PASSWORD"]
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
    kms_key_id  = aws_kms_key.cognito_email.arn

    custom_email_sender {
      lambda_arn     = aws_lambda_function.cognito_email_sender.arn
      lambda_version = "V1_0"
    }
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
  explicit_auth_flows                  = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  access_token_validity                = 15
  id_token_validity                    = 15
  refresh_token_validity               = 1

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
        Effect = "Allow"
        Action = ["sts:AssumeRole"]
        # The discovery role stays read-only. An execution role exists only
        # when a customer explicitly selected and acknowledged the separate
        # administrator-pilot connection path. Plan roles are granted only by
        # the separate verification and run-scoped credential-broker gates.
        Resource = [
          "arn:aws:iam::*:role/davdeployDiscovery-*",
          "arn:aws:iam::*:role/davdeployExecution-*",
        ]
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
      var.enable_nova_plan_role_verification ? [{
        # The API may verify only customer roles with the plan-only name prefix.
        # The customer role trust also requires this connection's ExternalId.
        Effect   = "Allow"
        Action   = ["sts:AssumeRole"]
        Resource = "arn:aws:iam::*:role/davdeployPlan-*"
        Condition = {
          StringLike = {
            "sts:ExternalId"      = "?*"
            "sts:RoleSessionName" = "davdeploy-plan-verify-*"
          }
        }
      }] : [],
      var.enable_nova_plan_credential_broker ? [{
        # Only the run-scoped broker can assume a customer plan role for the
        # exact active build. Its proposal-derived session policy is applied
        # to each AssumeRole call; this base grant stays off by default.
        Effect   = "Allow"
        Action   = ["sts:AssumeRole"]
        Resource = "arn:aws:iam::*:role/davdeployPlan-*"
        Condition = {
          StringLike = {
            "sts:ExternalId"      = "?*"
            "sts:RoleSessionName" = "davdeploy-nova-plan-*"
          }
        }
      }] : [],
      var.github_app_credential_secret_arn == "" ? [] : [{
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.github_app_credential_secret_arn
      }],
      var.ses_identity_arn == "" ? [] : [{
        Effect   = "Allow"
        Action   = ["ses:SendEmail"]
        Resource = var.ses_identity_arn
      }],
      var.resend_invitation_parameter_name == "" ? [] : [{
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${var.resend_invitation_parameter_name}"
      }],
      var.edge_origin_token_parameter_name == "" ? [] : [{
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${var.edge_origin_token_parameter_name}"
      }],
      var.enable_nova_plan_reviews ? [{
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObjectVersion"]
        Resource = "arn:aws:s3:::${var.nova_plan_artifact_bucket}/plans/nova-generated/*"
      }] : [],
      var.enable_nova_terraform_state_storage && var.enable_nova_terraform_state_api ? [{
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"]
        Resource = "${aws_s3_bucket.nova_terraform_state[0].arn}/terraform-state/*"
      }] : [],
      var.enable_nova_terraform_state_storage && var.enable_nova_terraform_state_api ? [{
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.nova_terraform_state[0].arn
        Condition = {
          StringEquals = {
            "kms:ViaService"                   = "s3.${var.region}.amazonaws.com"
            "kms:EncryptionContext:aws:s3:arn" = aws_s3_bucket.nova_terraform_state[0].arn
          }
        }
      }] : [],
      var.enable_nova_plan_reviews ? [{
        # Recovery can inspect only the dedicated Nova plan project. It cannot start builds.
        Effect   = "Allow"
        Action   = ["codebuild:ListBuildsForProject", "codebuild:BatchGetBuilds"]
        Resource = "arn:aws:codebuild:${var.region}:${data.aws_caller_identity.current.account_id}:project/${local.name}-nova-plan-only"
      }] : [],
      var.enable_nova_plan_reviews ? [{
        # HeadObject on the exact staged request uses s3:GetObject. Keep it
        # limited to input.json; no ListBucket permission is granted, so a 403
        # for a missing key remains uncertain and requires explicit attempt abandonment.
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::${var.nova_plan_artifact_bucket}/plans/nova-generated/requests/????????-????-????-????-????????????/input.json"
      }] : [],
      var.enable_nova_plan_reviews ? [{
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = var.nova_plan_kms_key_arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.region}.amazonaws.com"
            # The existing plans bucket enables S3 Bucket Keys, whose KMS
            # encryption context is the bucket ARN. S3 permissions above
            # independently restrict object access to the Nova prefix.
            "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::${var.nova_plan_artifact_bucket}"
          }
        }
      }] : []
    )
  })
}

resource "aws_iam_role_policy" "api_nova_plan_only_codebuild" {
  count = var.enable_nova_plan_only_runner ? 1 : 0

  name = "nova-plan-only-codebuild"
  role = aws_iam_role.api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["codebuild:StartBuild"]
        Resource = aws_codebuild_project.nova_plan_only[0].arn
        Condition = {
          Null = {
            "codebuild:environment.environmentVariables.name"                             = "false"
            "codebuild:environment.environmentVariables/DAVDEPLOY_NOVA_PLAN_RUN_ID.value" = "false"
          }
          "ForAllValues:StringEquals" = {
            "codebuild:environment.environmentVariables.name" = ["DAVDEPLOY_NOVA_PLAN_RUN_ID"]
          }
          StringLike = {
            "codebuild:environment.environmentVariables/DAVDEPLOY_NOVA_PLAN_RUN_ID.value" = "?*"
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["codebuild:BatchGetBuilds"]
        Resource = aws_codebuild_project.nova_plan_only[0].arn
      },
      {
        Effect   = "Deny"
        Action   = ["codebuild:StartBuild"]
        Resource = aws_codebuild_project.nova_plan_only[0].arn
        Condition = {
          "ForAnyValue:StringNotEquals" = {
            "codebuild:environment.environmentVariables.name" = ["DAVDEPLOY_NOVA_PLAN_RUN_ID"]
          }
        }
      }
    ]
  })
}

# Keep the explicit StartBuild override denies on a separate managed policy.
# The API role already has several inline policies, whose aggregate AWS limit
# is 10,240 bytes; the fixed deny list must not be removed to fit that limit.
data "aws_iam_policy" "api_nova_plan_only_start_build_overrides" {
  arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:policy/nova-plan-only-start-build-overrides"
}

resource "aws_iam_role_policy_attachment" "api_nova_plan_only_start_build_overrides" {
  count = var.enable_nova_plan_only_runner ? 1 : 0

  role       = aws_iam_role.api.name
  policy_arn = data.aws_iam_policy.api_nova_plan_only_start_build_overrides.arn
}

data "aws_iam_policy" "api_nova_exact_plan_apply_codebuild" {
  count = var.enable_nova_exact_plan_apply_runner ? 1 : 0

  arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:policy/nova-exact-plan-apply-codebuild"
}

resource "aws_iam_role_policy_attachment" "api_nova_exact_plan_apply_codebuild" {
  count = var.enable_nova_exact_plan_apply_runner ? 1 : 0

  role       = aws_iam_role.api.name
  policy_arn = data.aws_iam_policy.api_nova_exact_plan_apply_codebuild[0].arn
}

data "aws_iam_policy" "api_nova_exact_plan_apply_start_build_overrides" {
  count = var.enable_nova_exact_plan_apply_runner ? 1 : 0

  arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:policy/nova-exact-plan-apply-start-build-overrides"
}

resource "aws_iam_role_policy_attachment" "api_nova_exact_plan_apply_start_build_overrides" {
  count = var.enable_nova_exact_plan_apply_runner ? 1 : 0

  role       = aws_iam_role.api.name
  policy_arn = data.aws_iam_policy.api_nova_exact_plan_apply_start_build_overrides[0].arn
}

resource "aws_iam_role_policy" "api_nova_exact_plan_apply_artifacts" {
  count = var.enable_nova_exact_plan_apply_runner ? 1 : 0

  name = "nova-exact-plan-apply-artifacts"
  role = aws_iam_role.api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_exact_plan_apply_input_key}"
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption"                = "aws:kms"
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = var.nova_plan_kms_key_arn
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObjectVersion"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_exact_plan_apply_input_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_exact_plan_apply_build_result_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey", "kms:Decrypt"]
        Resource = var.nova_plan_kms_key_arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.region}.${data.aws_partition.current.dns_suffix}"
          }
          StringLike = {
            "kms:EncryptionContext:aws:s3:arn" = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "api_nova_plan_only_artifacts" {
  count = var.enable_nova_plan_only_runner ? 1 : 0

  name = "nova-plan-only-artifacts"
  role = aws_iam_role.api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_plan_only_input_key}"
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption"                = "aws:kms"
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = var.nova_plan_kms_key_arn
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_plan_only_build_input_key}"
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption"                = "aws:kms"
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = var.nova_plan_kms_key_arn
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_plan_only_build_result_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObjectVersion"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_plan_only_input_key}"
      },
      {
        # Recovery can inspect the current immutable build-input object and
        # read its exact version. Both actions are limited to that exact key.
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_plan_only_build_input_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObjectVersion"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_plan_only_build_saved_plan_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObjectVersion"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_plan_only_build_workspace_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey"]
        Resource = var.nova_plan_kms_key_arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.region}.${data.aws_partition.current.dns_suffix}"
          }
          StringLike = {
            # The plans bucket enables S3 Bucket Keys, so KMS receives the bucket ARN.
            # Per-build isolation remains enforced by the S3 object Resource ARNs.
            "kms:EncryptionContext:aws:s3:arn" = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}"
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = var.nova_plan_kms_key_arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.region}.${data.aws_partition.current.dns_suffix}"
          }
          StringLike = {
            "kms:EncryptionContext:aws:s3:arn" = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}"
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = var.nova_plan_kms_key_arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.region}.${data.aws_partition.current.dns_suffix}"
          }
          StringLike = {
            "kms:EncryptionContext:aws:s3:arn" = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}"
          }
        }
      },
    ]
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
            - bash scripts/customer-workload-dispatcher.sh
    EOT
  }

  tags = merge(local.common_tags, { Purpose = "bounded-customer-terraform-execution" })
}

resource "aws_iam_role" "nova_plan_only" {
  count = var.enable_nova_plan_only_runner ? 1 : 0

  name = "${local.name}-nova-plan-only"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "codebuild.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
        ArnEquals = {
          "aws:SourceArn" = "arn:${data.aws_partition.current.partition}:codebuild:${var.region}:${data.aws_caller_identity.current.account_id}:project/${local.nova_plan_only_project_name}"
        }
      }
    }]
  })
  tags = merge(local.common_tags, { Purpose = "isolated-nova-plan-only-runner" })
}

resource "aws_iam_role_policy" "nova_plan_only" {
  count = var.enable_nova_plan_only_runner ? 1 : 0

  name = "isolated-nova-plan-only-artifacts"
  role = aws_iam_role.nova_plan_only[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.nova_plan_only[0].arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_plan_only_scoped_input_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_plan_only_scoped_result_key}"
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption"                = "aws:kms"
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = var.nova_plan_kms_key_arn
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_plan_only_scoped_saved_plan_key}"
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption"                = "aws:kms"
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = var.nova_plan_kms_key_arn
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_plan_only_scoped_workspace_key}"
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption"                = "aws:kms"
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = var.nova_plan_kms_key_arn
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = var.nova_plan_kms_key_arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.region}.${data.aws_partition.current.dns_suffix}"
          }
          StringLike = {
            "kms:EncryptionContext:aws:s3:arn" = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}"
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey"]
        Resource = var.nova_plan_kms_key_arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.region}.${data.aws_partition.current.dns_suffix}"
          }
          StringLike = {
            "kms:EncryptionContext:aws:s3:arn" = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}"
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObjectVersion"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.artifact_bucket}/${var.artifact_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = var.nova_plan_runner_release_kms_key_arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.region}.${data.aws_partition.current.dns_suffix}"
          }
          StringLike = {
            "kms:EncryptionContext:aws:s3:arn" = [
              "arn:${data.aws_partition.current.partition}:s3:::${var.artifact_bucket}",
              "arn:${data.aws_partition.current.partition}:s3:::${var.artifact_bucket}/${var.artifact_key}",
            ]
          }
        }
      },
    ]
  })
}

resource "aws_iam_role" "nova_exact_plan_apply" {
  count = var.enable_nova_exact_plan_apply_runner ? 1 : 0

  name = "${local.name}-nova-saved-plan-apply"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "codebuild.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
        ArnEquals = {
          "aws:SourceArn" = "arn:${data.aws_partition.current.partition}:codebuild:${var.region}:${data.aws_caller_identity.current.account_id}:project/${local.nova_exact_plan_apply_project_name}"
        }
      }
    }]
  })
  tags = merge(local.common_tags, { Purpose = "isolated-nova-exact-plan-apply-runner" })
}

resource "aws_iam_role_policy" "nova_exact_plan_apply" {
  count = var.enable_nova_exact_plan_apply_runner ? 1 : 0

  name = "isolated-nova-exact-plan-apply-artifacts"
  role = aws_iam_role.nova_exact_plan_apply[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.nova_exact_plan_apply[0].arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_exact_plan_apply_input_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_exact_plan_apply_scoped_result_key}"
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption"                = "aws:kms"
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = var.nova_plan_kms_key_arn
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObjectVersion"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_exact_plan_apply_scoped_plan_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObjectVersion"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}/${local.nova_exact_plan_apply_scoped_workspace_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = var.nova_plan_kms_key_arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.region}.${data.aws_partition.current.dns_suffix}"
          }
          StringLike = {
            "kms:EncryptionContext:aws:s3:arn" = "arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}"
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObjectVersion"]
        Resource = "arn:${data.aws_partition.current.partition}:s3:::${var.artifact_bucket}/${var.artifact_key}"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = var.nova_plan_runner_release_kms_key_arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.region}.${data.aws_partition.current.dns_suffix}"
          }
          StringLike = {
            "kms:EncryptionContext:aws:s3:arn" = [
              "arn:${data.aws_partition.current.partition}:s3:::${var.artifact_bucket}",
              "arn:${data.aws_partition.current.partition}:s3:::${var.artifact_bucket}/${var.artifact_key}",
            ]
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["execute-api:Invoke"]
        Resource = "${aws_apigatewayv2_api.control_plane.execution_arn}/*/POST/api/v1/nova-apply/credentials"
        Condition = {
          ArnLike = {
            "codebuild:BuildArn" = "arn:${data.aws_partition.current.partition}:codebuild:${var.region}:${data.aws_caller_identity.current.account_id}:build/${local.nova_exact_plan_apply_project_name}:*"
          }
        }
      },
    ]
  })
}

resource "aws_iam_role_policy" "nova_plan_credentials_bootstrap" {
  count = var.enable_nova_plan_credential_broker ? 1 : 0

  name = "nova-plan-credential-bootstrap"
  role = aws_iam_role.nova_plan_only[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["execute-api:Invoke"]
      Resource = "${aws_apigatewayv2_api.control_plane.execution_arn}/*/POST/api/v1/nova-plan/credentials"
      Condition = {
        ArnLike = {
          "codebuild:BuildArn" = "arn:${data.aws_partition.current.partition}:codebuild:${var.region}:${data.aws_caller_identity.current.account_id}:build/${local.nova_plan_only_project_name}:*"
        }
      }
    }]
  })
}

resource "aws_kms_key" "nova_terraform_state" {
  count = var.enable_nova_terraform_state_storage ? 1 : 0

  description             = "DavDeploy tenant-isolated Nova Terraform state"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = merge(local.common_tags, { Purpose = "nova-terraform-state" })

  lifecycle { prevent_destroy = true }
}

resource "aws_kms_alias" "nova_terraform_state" {
  count = var.enable_nova_terraform_state_storage ? 1 : 0

  name          = "alias/${local.name}-nova-terraform-state"
  target_key_id = aws_kms_key.nova_terraform_state[0].key_id
}

resource "aws_s3_bucket" "nova_terraform_state" {
  count = var.enable_nova_terraform_state_storage ? 1 : 0

  bucket        = "${local.name}-tfstate-${data.aws_caller_identity.current.account_id}-${var.region}"
  force_destroy = false
  tags          = merge(local.common_tags, { Purpose = "nova-terraform-state" })

  lifecycle { prevent_destroy = true }
}

resource "aws_s3_bucket_versioning" "nova_terraform_state" {
  count = var.enable_nova_terraform_state_storage ? 1 : 0

  bucket = aws_s3_bucket.nova_terraform_state[0].id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "nova_terraform_state" {
  count = var.enable_nova_terraform_state_storage ? 1 : 0

  bucket = aws_s3_bucket.nova_terraform_state[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.nova_terraform_state[0].arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "nova_terraform_state" {
  count = var.enable_nova_terraform_state_storage ? 1 : 0

  bucket                  = aws_s3_bucket.nova_terraform_state[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "nova_terraform_state" {
  count = var.enable_nova_terraform_state_storage ? 1 : 0

  bucket = aws_s3_bucket.nova_terraform_state[0].id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_policy" "nova_terraform_state" {
  count = var.enable_nova_terraform_state_storage ? 1 : 0

  bucket = aws_s3_bucket.nova_terraform_state[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.nova_terraform_state[0].arn,
        "${aws_s3_bucket.nova_terraform_state[0].arn}/*",
      ]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

resource "aws_iam_role_policy" "nova_plan_only_state_bootstrap" {
  count = var.enable_nova_terraform_state_api ? 1 : 0

  name = "nova-plan-only-state-bootstrap"
  role = aws_iam_role.nova_plan_only[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["execute-api:Invoke"]
      Resource = "${aws_apigatewayv2_api.control_plane.execution_arn}/*/POST/api/v1/terraform-state/credentials"
      Condition = {
        ArnLike = {
          "codebuild:BuildArn" = "arn:${data.aws_partition.current.partition}:codebuild:${var.region}:${data.aws_caller_identity.current.account_id}:build/${local.nova_plan_only_project_name}:*"
        }
      }
    }]
  })
}

resource "aws_cloudwatch_log_group" "nova_plan_only" {
  count = var.enable_nova_plan_only_runner ? 1 : 0

  name              = "/aws/codebuild/${local.nova_plan_only_project_name}"
  retention_in_days = 14
  tags              = merge(local.common_tags, { Purpose = "isolated-nova-plan-only-runner" })
}

resource "aws_codebuild_project" "nova_plan_only" {
  count = var.enable_nova_plan_only_runner ? 1 : 0

  name                   = local.nova_plan_only_project_name
  description            = "Fixed Nova Terraform plan-only runner; remote state is opt-in, with no approval, apply, or destroy."
  service_role           = aws_iam_role.nova_plan_only[0].arn
  build_timeout          = 15
  queued_timeout         = 5
  concurrent_build_limit = 1

  artifacts { type = "NO_ARTIFACTS" }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    privileged_mode             = false
    image_pull_credentials_type = "CODEBUILD"
    environment_variable {
      name  = "DAVDEPLOY_NOVA_PLAN_ARTIFACT_BUCKET"
      value = var.nova_plan_artifact_bucket
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_PLAN_KMS_KEY_ARN"
      value = var.nova_plan_kms_key_arn
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_PLAN_BUCKET_OWNER"
      value = data.aws_caller_identity.current.account_id
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_PLAN_PROJECT_NAME"
      value = local.nova_plan_only_project_name
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_PLAN_CREDENTIAL_BROKER_URL"
      value = var.enable_nova_plan_credential_broker ? "${aws_apigatewayv2_api.control_plane.api_endpoint}/api/v1/nova-plan/credentials" : ""
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_TERRAFORM_STATE_BOOTSTRAP_URL"
      value = "${aws_apigatewayv2_api.control_plane.api_endpoint}/api/v1/terraform-state/credentials"
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_TERRAFORM_STATE_ENABLED"
      value = tostring(var.enable_nova_terraform_state_api)
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_TERRAFORM_STATE_API_URL"
      value = var.enable_nova_terraform_state_api ? var.nova_terraform_state_api_url : ""
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_PLAN_CODE_BUCKET"
      value = var.artifact_bucket
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_PLAN_CODE_KEY"
      value = var.artifact_key
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_PLAN_CODE_VERSION"
      value = coalesce(var.artifact_object_version, "disabled")
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_PLAN_CODE_BUCKET_OWNER"
      value = data.aws_caller_identity.current.account_id
      type  = "PLAINTEXT"
    }
  }

  source {
    type      = "NO_SOURCE"
    buildspec = <<-EOT
      version: 0.2
      env:
        variables:
          DAVDEPLOY_NOVA_PLAN_RUNNER_RELEASE_VERSION: "1"
      phases:
        install:
          runtime-versions:
            python: 3.12
          commands:
            - mkdir -p /tmp/davdeploy-nova-runner/code /tmp/davdeploy-nova-runner/terraform
            - aws s3api get-object --bucket "$DAVDEPLOY_NOVA_PLAN_CODE_BUCKET" --key "$DAVDEPLOY_NOVA_PLAN_CODE_KEY" --version-id "$DAVDEPLOY_NOVA_PLAN_CODE_VERSION" --expected-bucket-owner "$DAVDEPLOY_NOVA_PLAN_CODE_BUCKET_OWNER" /tmp/davdeploy-nova-runner/code.zip >/dev/null
            - unzip -q /tmp/davdeploy-nova-runner/code.zip -d /tmp/davdeploy-nova-runner/code
            - curl -fsSL -o /tmp/davdeploy-nova-runner/terraform.zip https://releases.hashicorp.com/terraform/1.14.7/terraform_1.14.7_linux_amd64.zip
            - echo "e8bbcefea8015156e04e2a325cde37a0b2fb761728bda548e2fe3b8ad7c18c96  /tmp/davdeploy-nova-runner/terraform.zip" | sha256sum --check --status
            - unzip -q /tmp/davdeploy-nova-runner/terraform.zip -d /tmp/davdeploy-nova-runner/terraform
            - chmod 700 /tmp/davdeploy-nova-runner/terraform/terraform
        build:
          commands:
            - PATH="/tmp/davdeploy-nova-runner/terraform:$PATH" PYTHONPATH="/tmp/davdeploy-nova-runner/code" python3.12 -m davdeploy.nova_plan_codebuild
    EOT
  }

  logs_config {
    cloudwatch_logs {
      group_name  = aws_cloudwatch_log_group.nova_plan_only[0].name
      stream_name = "build"
      status      = "ENABLED"
    }
    s3_logs { status = "DISABLED" }
  }

  tags = merge(local.common_tags, { Purpose = "isolated-nova-plan-only-runner" })
}

resource "aws_cloudwatch_log_group" "nova_exact_plan_apply" {
  count = var.enable_nova_exact_plan_apply_runner ? 1 : 0

  name              = "/aws/codebuild/${local.nova_exact_plan_apply_project_name}"
  retention_in_days = 14
  tags              = merge(local.common_tags, { Purpose = "isolated-nova-exact-plan-apply-runner" })
}

resource "aws_codebuild_project" "nova_exact_plan_apply" {
  count = var.enable_nova_exact_plan_apply_runner ? 1 : 0

  name                   = local.nova_exact_plan_apply_project_name
  description            = "Separate fixed CodeBuild boundary for future exact approved-plan apply; no customer apply is wired by this disabled project."
  service_role           = aws_iam_role.nova_exact_plan_apply[0].arn
  build_timeout          = 120
  queued_timeout         = 5
  concurrent_build_limit = 1

  artifacts { type = "NO_ARTIFACTS" }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    privileged_mode             = false
    image_pull_credentials_type = "CODEBUILD"
    environment_variable {
      name  = "DAVDEPLOY_NOVA_APPLY_ARTIFACT_BUCKET"
      value = var.nova_plan_artifact_bucket
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_APPLY_KMS_KEY_ARN"
      value = var.nova_plan_kms_key_arn
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_APPLY_BUCKET_OWNER"
      value = data.aws_caller_identity.current.account_id
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_APPLY_PROJECT_NAME"
      value = local.nova_exact_plan_apply_project_name
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_APPLY_CREDENTIAL_BROKER_URL"
      value = "${aws_apigatewayv2_api.control_plane.api_endpoint}/api/v1/nova-apply/credentials"
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_APPLY_CODE_BUCKET"
      value = var.artifact_bucket
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_APPLY_CODE_KEY"
      value = var.artifact_key
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_APPLY_CODE_VERSION"
      value = coalesce(var.artifact_object_version, "disabled")
      type  = "PLAINTEXT"
    }
    environment_variable {
      name  = "DAVDEPLOY_NOVA_APPLY_CODE_BUCKET_OWNER"
      value = data.aws_caller_identity.current.account_id
      type  = "PLAINTEXT"
    }
  }

  source {
    type      = "NO_SOURCE"
    buildspec = <<-EOT
      version: 0.2
      phases:
        install:
          commands:
            - echo "The fixed Nova exact-plan apply worker is not wired." >&2
            - exit 1
    EOT
  }

  logs_config {
    cloudwatch_logs {
      group_name  = aws_cloudwatch_log_group.nova_exact_plan_apply[0].name
      stream_name = "build"
      status      = "ENABLED"
    }
    s3_logs { status = "DISABLED" }
  }

  tags = merge(local.common_tags, { Purpose = "isolated-nova-exact-plan-apply-runner" })
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

resource "aws_kms_key" "cognito_email" {
  description             = "DavDeploy Cognito custom-email sender code encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = local.common_tags
}

resource "aws_iam_role" "cognito_email_sender" {
  name = "${local.name}-cognito-email-sender"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "cognito_email_sender_logs" {
  role       = aws_iam_role.cognito_email_sender.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "cognito_email_sender" {
  name = "send-cognito-email-through-resend"
  role = aws_iam_role.cognito_email_sender.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = aws_kms_key.cognito_email.arn
      }
      ], var.resend_invitation_parameter_name == "" ? [] : [{
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${var.resend_invitation_parameter_name}"
    }])
  })
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
  lambda_log_groups = toset(["api", "cognito-email-sender", "cognito-link", "migrate", "policy", "worker"])
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = local.lambda_log_groups
  name              = "/aws/lambda/${local.name}-${each.value}"
  retention_in_days = 14
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${local.name}"
  retention_in_days = 30
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

resource "aws_lambda_function" "cognito_email_sender" {
  function_name     = "${local.name}-cognito-email-sender"
  role              = aws_iam_role.cognito_email_sender.arn
  runtime           = "python3.12"
  handler           = "davdeploy.lambda_cognito_email_sender.handler"
  s3_bucket         = var.artifact_bucket
  s3_key            = var.artifact_key
  s3_object_version = var.artifact_object_version
  timeout           = 15
  memory_size       = 256
  environment {
    variables = {
      DAVDEPLOY_COGNITO_EMAIL_KMS_KEY_ARN    = aws_kms_key.cognito_email.arn
      DAVDEPLOY_RESEND_API_KEY_SSM_PARAMETER = var.resend_invitation_parameter_name
      DAVDEPLOY_RESEND_FROM_ADDRESS          = "DavDeploy <notify@davdeploy.tech>"
      DAVDEPLOY_RESEND_REPLY_TO_ADDRESS      = "support@davdeploy.tech"
    }
  }
  tags       = local.common_tags
  depends_on = [aws_cloudwatch_log_group.lambda]
}

resource "aws_lambda_permission" "cognito_email_sender" {
  statement_id  = "AllowCognitoEmailSender"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cognito_email_sender.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.identity.arn
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
    DAVDEPLOY_HOSTED_MODE                                = "true"
    DAVDEPLOY_AUTO_MIGRATE                               = "false"
    DAVDEPLOY_AURORA_CLUSTER_ARN                         = aws_rds_cluster.control_plane.arn
    DAVDEPLOY_DATABASE_SECRET_ARN                        = aws_rds_cluster.control_plane.master_user_secret[0].secret_arn
    DAVDEPLOY_DATABASE_NAME                              = var.database_name
    DAVDEPLOY_ALLOWED_FRONTEND_ORIGINS                   = var.frontend_origin
    DAVDEPLOY_RATE_LIMIT_PER_MINUTE                      = tostring(var.application_rate_limit_per_minute)
    DAVDEPLOY_JWKS_URL                                   = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.identity.id}/.well-known/jwks.json"
    DAVDEPLOY_OIDC_ISSUER                                = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.identity.id}"
    DAVDEPLOY_OIDC_AUDIENCE                              = aws_cognito_user_pool_client.frontend.id
    DAVDEPLOY_POLICY_FUNCTION_ARN                        = aws_lambda_function.policy.arn
    DAVDEPLOY_MODEL_PROVIDER                             = "bedrock"
    DAVDEPLOY_ENABLE_NOVA_MODEL                          = "true"
    DAVDEPLOY_BEDROCK_MODEL_ID                           = var.nova_model_id
    DAVDEPLOY_EXECUTOR_MODE                              = "embedded_fixture"
    DAVDEPLOY_EMAIL_PROVIDER                             = var.resend_invitation_parameter_name != "" ? "resend" : (var.ses_identity_arn == "" ? "disabled" : "ses")
    DAVDEPLOY_SES_FROM_ADDRESS                           = var.ses_from_address
    DAVDEPLOY_RESEND_API_KEY_SSM_PARAMETER               = var.resend_invitation_parameter_name
    DAVDEPLOY_RESEND_FROM_ADDRESS                        = var.resend_invitation_parameter_name == "" ? "" : "DavDeploy <notify@davdeploy.tech>"
    DAVDEPLOY_RESEND_REPLY_TO_ADDRESS                    = var.resend_invitation_parameter_name == "" ? "" : "support@davdeploy.tech"
    DAVDEPLOY_EDGE_ORIGIN_TOKEN_SSM_PARAMETER            = var.edge_origin_token_parameter_name
    DAVDEPLOY_FRONTEND_ORIGIN                            = var.frontend_origin
    DAVDEPLOY_CONNECTION_SECRET_BACKEND                  = "aws_secrets_manager"
    DAVDEPLOY_CONNECTION_SECRET_PREFIX                   = "davdeploy/customer-connections"
    DAVDEPLOY_AWS_LIVE_DISCOVERY_ENABLED                 = "true"
    DAVDEPLOY_DISCOVERY_BROKER_ROLE_ARN                  = aws_iam_role.api.arn
    DAVDEPLOY_EXECUTION_BROKER_ROLE_ARN                  = aws_iam_role.customer_executor.arn
    DAVDEPLOY_NOVA_PLAN_PROJECT                          = var.enable_nova_plan_only_runner ? aws_codebuild_project.nova_plan_only[0].name : ""
    DAVDEPLOY_NOVA_PLAN_ONLY_ROLE_ARN                    = var.enable_nova_plan_only_runner ? aws_iam_role.nova_plan_only[0].arn : ""
    DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_PROJECT              = var.enable_nova_exact_plan_apply_runner ? aws_codebuild_project.nova_exact_plan_apply[0].name : ""
    DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_RUNNER_READY         = tostring(var.enable_nova_exact_plan_apply_runner)
    DAVDEPLOY_TERRAFORM_STATE_ENABLED                    = tostring(var.enable_nova_terraform_state_api)
    DAVDEPLOY_TERRAFORM_STATE_API_URL                    = var.enable_nova_terraform_state_api ? var.nova_terraform_state_api_url : ""
    DAVDEPLOY_TERRAFORM_STATE_BUCKET                     = var.enable_nova_terraform_state_storage ? aws_s3_bucket.nova_terraform_state[0].bucket : ""
    DAVDEPLOY_TERRAFORM_STATE_KMS_KEY_ARN                = var.enable_nova_terraform_state_storage ? aws_kms_key.nova_terraform_state[0].arn : ""
    DAVDEPLOY_TERRAFORM_STATE_BUCKET_OWNER               = var.enable_nova_terraform_state_storage ? data.aws_caller_identity.current.account_id : ""
    DAVDEPLOY_NOVA_PLAN_RUNNER_READY                     = tostring(var.enable_nova_plan_only_runner)
    DAVDEPLOY_NOVA_PLAN_ROLE_VERIFY_ENABLED              = tostring(var.enable_nova_plan_role_verification)
    DAVDEPLOY_NOVA_PLAN_CREDENTIAL_BROKER_ENABLED        = tostring(var.enable_nova_plan_credential_broker)
    DAVDEPLOY_AWS_CONNECTION_TEMPLATE_URL                = var.aws_connection_template_url
    DAVDEPLOY_CUSTOMER_EXECUTOR_PROJECT                  = aws_codebuild_project.customer_executor.name
    DAVDEPLOY_CLOUD_EXECUTION_BACKEND                    = "codebuild"
    DAVDEPLOY_CLOUD_EXECUTION_COMMAND_ENABLED            = tostring(var.enable_customer_cloud_execution)
    DAVDEPLOY_ENABLE_APP_RUNNER_EXECUTION                = tostring(var.enable_customer_cloud_execution)
    DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION = tostring(var.enable_serverless_api_hosted_certification)
    DAVDEPLOY_SERVERLESS_CERTIFICATION_WORKSPACE_IDS     = join(",", var.serverless_certification_workspace_ids)
    ALLOW_CLOUD_PLAN                                     = tostring(var.enable_customer_cloud_execution)
    ALLOW_CLOUD_APPLY                                    = tostring(var.enable_customer_cloud_execution)
    DAVDEPLOY_CUSTOMER_EXECUTION_ARTIFACT_S3_URI         = "s3://${var.artifact_bucket}/${var.customer_execution_artifact_key}"
    DAVDEPLOY_CUSTOMER_EXECUTION_STATE_BUCKET            = var.customer_execution_state_bucket
    DAVDEPLOY_CUSTOMER_EXECUTION_LOCK_TABLE              = var.customer_execution_lock_table
    DAVDEPLOY_NOVA_PLAN_REVIEWS_ENABLED                  = tostring(var.enable_nova_plan_reviews)
    DAVDEPLOY_NOVA_PLAN_ARTIFACT_BUCKET                  = var.nova_plan_artifact_bucket
    DAVDEPLOY_NOVA_PLAN_KMS_KEY_ARN                      = var.nova_plan_kms_key_arn
    DAVDEPLOY_NOVA_PLAN_BUCKET_OWNER                     = data.aws_caller_identity.current.account_id
    DAVDEPLOY_WORKER_QUEUE_URL                           = aws_sqs_queue.worker.id
    DAVDEPLOY_GITHUB_APP_READ_ONLY                       = tostring(var.enable_github_app_read_only)
    DAVDEPLOY_GITHUB_APP_ID                              = var.github_app_id
    DAVDEPLOY_GITHUB_APP_INSTALLATION_ID                 = var.github_app_installation_id
    DAVDEPLOY_GITHUB_APP_CREDENTIAL_SECRET_ARN           = var.github_app_credential_secret_arn
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

# The bootstrap request must be signed by the isolated CodeBuild role. API
# Gateway overwrites this header from the authenticated IAM identity, so a
# caller cannot select its own role by supplying a header value.
resource "aws_apigatewayv2_integration" "terraform_state_bootstrap" {
  api_id                 = aws_apigatewayv2_api.control_plane.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
  request_parameters = {
    "overwrite:header.x-davdeploy-bootstrap-principal" = "$context.identity.userArn"
  }
}

# API Gateway authenticates the fixed plan worker and overwrites its principal
# header before the Lambda can issue customer role credentials.
resource "aws_apigatewayv2_integration" "nova_plan_credentials" {
  api_id                 = aws_apigatewayv2_api.control_plane.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
  request_parameters = {
    "overwrite:header.x-davdeploy-bootstrap-principal" = "$context.identity.userArn"
  }
}

resource "aws_apigatewayv2_route" "authenticated" {
  api_id             = aws_apigatewayv2_api.control_plane.id
  route_key          = "$default"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "terraform_state_bootstrap" {
  api_id             = aws_apigatewayv2_api.control_plane.id
  route_key          = "POST /api/v1/terraform-state/credentials"
  target             = "integrations/${aws_apigatewayv2_integration.terraform_state_bootstrap.id}"
  authorization_type = "AWS_IAM"
}

resource "aws_apigatewayv2_route" "nova_plan_credentials" {
  api_id             = aws_apigatewayv2_api.control_plane.id
  route_key          = "POST /api/v1/nova-plan/credentials"
  target             = "integrations/${aws_apigatewayv2_integration.nova_plan_credentials.id}"
  authorization_type = "AWS_IAM"
}

locals {
  # Terraform authenticates these calls with the short-lived Basic credential
  # checked by the API. The edge-origin middleware remains required for state
  # traffic; the direct API Gateway IAM exception exists only for bootstrap.
  terraform_state_routes = toset([
    "GET /api/v1/terraform-state/{state_id}",
    "POST /api/v1/terraform-state/{state_id}",
    "POST /api/v1/terraform-state/{state_id}/lock",
    "DELETE /api/v1/terraform-state/{state_id}/unlock",
  ])
}

resource "aws_apigatewayv2_route" "terraform_state" {
  for_each = local.terraform_state_routes

  api_id             = aws_apigatewayv2_api.control_plane.id
  route_key          = each.value
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "NONE"
}

locals {
  # API Gateway can throttle only declared routes. These routes take precedence over
  # the authenticated $default route and retain its exact integration and JWT boundary.
  sensitive_api_route_limits = {
    "POST /api/v1/workspace/invitations" = {
      burst = 3
      rate  = 1
    }
    "POST /api/v1/workspace/invitations/{invitation_id}/resend" = {
      burst = 2
      rate  = 1
    }
    "POST /api/v1/intents" = {
      burst = 3
      rate  = 1
    }
    "POST /api/v1/intents/{intent_id}/plans" = {
      burst = 2
      rate  = 0.5
    }
    "POST /api/v1/cloud-connections/{connection_id}/aws-verify" = {
      burst = 1
      rate  = 0.2
    }
    "POST /api/v1/support/tickets" = {
      burst = 3
      rate  = 1
    }
    "POST /api/v1/api-credentials" = {
      burst = 3
      rate  = 1
    }
    "DELETE /api/v1/api-credentials/{credential_id}" = {
      burst = 3
      rate  = 1
    }
  }
}

resource "aws_apigatewayv2_route" "sensitive" {
  for_each = local.sensitive_api_route_limits

  api_id             = aws_apigatewayv2_api.control_plane.id
  route_key          = each.key
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.control_plane.id
  route_key = "GET /healthz"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

# Public editorial reading is intentionally explicit. All writes, team authoring,
# and comment changes continue through the JWT-protected $default route.
locals {
  public_blog_read_routes = toset([
    "GET /api/v1/blog/posts",
    "GET /api/v1/blog/posts/{slug}",
    "GET /api/v1/blog/posts/{slug}/comments",
  ])
}

resource "aws_apigatewayv2_route" "public_blog_read" {
  for_each = local.public_blog_read_routes

  api_id    = aws_apigatewayv2_api.control_plane.id
  route_key = each.value
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

  # API Gateway rejects route-level settings until every referenced route exists.
  # Keep the stage update after creation when this map introduces a new route.
  depends_on = [
    aws_apigatewayv2_route.sensitive,
    aws_apigatewayv2_route.terraform_state_bootstrap,
    aws_apigatewayv2_route.nova_plan_credentials,
    aws_apigatewayv2_route.terraform_state,
  ]

  default_route_settings {
    throttling_burst_limit = 50
    throttling_rate_limit  = 25
  }

  # These routes trigger email delivery, model work, cloud API calls, or credentials.
  # Gateway enforcement is shared across Lambda instances and happens before application work.
  dynamic "route_settings" {
    for_each = local.sensitive_api_route_limits

    content {
      route_key              = route_settings.key
      throttling_burst_limit = route_settings.value.burst
      throttling_rate_limit  = route_settings.value.rate
    }
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      routeKey         = "$context.routeKey"
      status           = "$context.status"
      integrationError = "$context.integrationErrorMessage"
    })
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
    Statement = concat(
      [{
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.worker.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.customer_executor_completion.arn
          }
        }
      }],
      var.enable_nova_plan_only_runner ? [{
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.worker.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.nova_plan_only_completion[0].arn
          }
        }
      }] : [],
      var.enable_nova_exact_plan_apply_runner ? [{
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.worker.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.nova_exact_plan_apply_completion[0].arn
          }
        }
      }] : []
    )
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

resource "aws_cloudwatch_event_rule" "nova_plan_only_completion" {
  count = var.enable_nova_plan_only_runner ? 1 : 0

  name = "${local.name}-nova-plan-only-completion"
  event_pattern = jsonencode({
    source        = ["aws.codebuild"]
    "detail-type" = ["CodeBuild Build State Change"]
    detail = {
      "project-name" = [aws_codebuild_project.nova_plan_only[0].name]
      "build-status" = ["SUCCEEDED", "FAILED", "FAULT", "TIMED_OUT", "STOPPED"]
    }
  })
  tags = merge(local.common_tags, { Purpose = "isolated-nova-plan-only-runner" })
}

resource "aws_cloudwatch_event_target" "nova_plan_only_completion" {
  count = var.enable_nova_plan_only_runner ? 1 : 0

  rule       = aws_cloudwatch_event_rule.nova_plan_only_completion[0].name
  arn        = aws_sqs_queue.worker.arn
  depends_on = [aws_sqs_queue_policy.worker_events]
}

resource "aws_cloudwatch_event_rule" "nova_exact_plan_apply_completion" {
  count = var.enable_nova_exact_plan_apply_runner ? 1 : 0

  name = "${local.name}-nova-exact-plan-apply-completion"
  event_pattern = jsonencode({
    source        = ["aws.codebuild"]
    "detail-type" = ["CodeBuild Build State Change"]
    detail = {
      "project-name" = [aws_codebuild_project.nova_exact_plan_apply[0].name]
      "build-status" = ["SUCCEEDED", "FAILED", "FAULT", "TIMED_OUT", "STOPPED"]
    }
  })
  tags = merge(local.common_tags, { Purpose = "isolated-nova-exact-plan-apply-runner" })
}

resource "aws_cloudwatch_event_target" "nova_exact_plan_apply_completion" {
  count = var.enable_nova_exact_plan_apply_runner ? 1 : 0

  rule       = aws_cloudwatch_event_rule.nova_exact_plan_apply_completion[0].name
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

resource "aws_cloudwatch_log_metric_filter" "api_unauthorized" {
  name           = "${local.name}-api-unauthorized"
  log_group_name = aws_cloudwatch_log_group.api_gateway.name
  pattern        = "{ $.status = 401 }"

  metric_transformation {
    name          = "UnauthorizedResponses"
    namespace     = "DavDeploy/Security"
    value         = "1"
    default_value = 0
  }
}

resource "aws_cloudwatch_log_metric_filter" "api_forbidden" {
  name           = "${local.name}-api-forbidden"
  log_group_name = aws_cloudwatch_log_group.api_gateway.name
  pattern        = "{ $.status = 403 }"

  metric_transformation {
    name          = "ForbiddenResponses"
    namespace     = "DavDeploy/Security"
    value         = "1"
    default_value = 0
  }
}

resource "aws_cloudwatch_log_metric_filter" "api_throttled" {
  name           = "${local.name}-api-throttled"
  log_group_name = aws_cloudwatch_log_group.api_gateway.name
  pattern        = "{ $.status = 429 }"

  metric_transformation {
    name          = "ThrottledResponses"
    namespace     = "DavDeploy/Security"
    value         = "1"
    default_value = 0
  }
}

resource "aws_cloudwatch_metric_alarm" "api_unauthorized_burst" {
  alarm_name          = "${local.name}-api-unauthorized-burst"
  alarm_description   = "Repeated unauthenticated API requests may indicate a broken client or credential attack."
  namespace           = "DavDeploy/Security"
  metric_name         = "UnauthorizedResponses"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "api_forbidden_burst" {
  alarm_name          = "${local.name}-api-forbidden-burst"
  alarm_description   = "Repeated denied API actions may indicate authorization probing or a broken client."
  namespace           = "DavDeploy/Security"
  metric_name         = "ForbiddenResponses"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "api_throttled_burst" {
  alarm_name          = "${local.name}-api-throttled-burst"
  alarm_description   = "Repeated API throttling may indicate abusive traffic or an undersized client retry policy."
  namespace           = "DavDeploy/Security"
  metric_name         = "ThrottledResponses"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "cognito_failed_sign_in_burst" {
  alarm_name          = "${local.name}-cognito-failed-sign-in-burst"
  alarm_description   = "Repeated Cognito sign-in failures may indicate a broken client or authentication attack."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 10
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  tags                = local.common_tags

  metric_query {
    id          = "failed_signins"
    expression  = "sign_in_attempts - successful_signins"
    label       = "Failed Cognito sign-ins"
    return_data = true
  }

  metric_query {
    id = "sign_in_attempts"
    metric {
      namespace   = "AWS/Cognito"
      metric_name = "SignInSuccesses"
      stat        = "SampleCount"
      period      = 300
      dimensions = {
        UserPool       = aws_cognito_user_pool.identity.id
        UserPoolClient = aws_cognito_user_pool_client.frontend.id
      }
    }
  }

  metric_query {
    id = "successful_signins"
    metric {
      namespace   = "AWS/Cognito"
      metric_name = "SignInSuccesses"
      stat        = "Sum"
      period      = 300
      dimensions = {
        UserPool       = aws_cognito_user_pool.identity.id
        UserPoolClient = aws_cognito_user_pool_client.frontend.id
      }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "cognito_sign_in_throttles" {
  alarm_name          = "${local.name}-cognito-sign-in-throttles"
  alarm_description   = "Cognito throttled sign-in requests. Investigate abuse or client retry behavior."
  namespace           = "AWS/Cognito"
  metric_name         = "SignInThrottles"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  dimensions = {
    UserPool       = aws_cognito_user_pool.identity.id
    UserPoolClient = aws_cognito_user_pool_client.frontend.id
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
