data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_s3_bucket" "state" {
  bucket = var.state_bucket_name
}

data "aws_dynamodb_table" "lock" {
  name = var.lock_table_name
}

data "aws_iam_openid_connect_provider" "github" {
  arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
}

locals {
  plan_bucket_name    = "davdeploy-tfplans-${data.aws_caller_identity.current.account_id}"
  release_bucket_name = "davdeploy-releases-${data.aws_caller_identity.current.account_id}"
  common_tags = {
    Product   = "davdeploy"
    ManagedBy = "Terraform"
    Scope     = "terraform-operations"
  }
}

resource "aws_kms_key" "plans" {
  description             = "Encrypt davdeploy saved Terraform plans"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = merge(local.common_tags, { Purpose = "saved-plans" })
}

resource "aws_kms_alias" "plans" {
  name          = "alias/davdeploy-terraform-plans"
  target_key_id = aws_kms_key.plans.key_id
}

resource "aws_kms_key" "releases" {
  description             = "Encrypt immutable davdeploy Lambda releases"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = merge(local.common_tags, { Purpose = "lambda-releases" })
}

resource "aws_kms_alias" "releases" {
  name          = "alias/davdeploy-lambda-releases"
  target_key_id = aws_kms_key.releases.key_id
}

resource "aws_s3_bucket" "plans" {
  bucket = local.plan_bucket_name
  tags   = merge(local.common_tags, { Purpose = "saved-plans" })
}

resource "aws_s3_bucket_ownership_controls" "plans" {
  bucket = aws_s3_bucket.plans.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "plans" {
  bucket                  = aws_s3_bucket.plans.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "plans" {
  bucket = aws_s3_bucket.plans.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "plans" {
  bucket = aws_s3_bucket.plans.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.plans.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "plans" {
  bucket = aws_s3_bucket.plans.id
  rule {
    id     = "expire-saved-plans"
    status = "Enabled"
    filter {}
    expiration {
      days = var.plan_retention_days
    }
    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
  depends_on = [aws_s3_bucket_versioning.plans]
}

resource "aws_s3_bucket_policy" "plans" {
  bucket = aws_s3_bucket.plans.id
  policy = data.aws_iam_policy_document.plans_bucket.json
}

data "aws_iam_policy_document" "plans_bucket" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.plans.arn,
      "${aws_s3_bucket.plans.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket" "releases" {
  bucket = local.release_bucket_name
  tags   = merge(local.common_tags, { Purpose = "lambda-releases" })
}

resource "aws_s3_bucket_ownership_controls" "releases" {
  bucket = aws_s3_bucket.releases.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "releases" {
  bucket                  = aws_s3_bucket.releases.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "releases" {
  bucket = aws_s3_bucket.releases.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "releases" {
  bucket = aws_s3_bucket.releases.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.releases.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "releases" {
  bucket = aws_s3_bucket.releases.id
  rule {
    id     = "expire-old-releases"
    status = "Enabled"
    filter {}
    expiration {
      days = var.release_retention_days
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
  depends_on = [aws_s3_bucket_versioning.releases]
}

resource "aws_s3_bucket_policy" "releases" {
  bucket = aws_s3_bucket.releases.id
  policy = data.aws_iam_policy_document.releases_bucket.json
}

data "aws_iam_policy_document" "releases_bucket" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.releases.arn,
      "${aws_s3_bucket.releases.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

data "aws_iam_policy_document" "plan_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${var.github_oidc_repository_subject}:environment:terraform-plan"]
    }
  }
}

data "aws_iam_policy_document" "apply_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${var.github_oidc_repository_subject}:environment:terraform-apply"]
    }
  }
}

resource "aws_iam_role" "plan" {
  name                 = "davdeploy-terraform-plan-github"
  description          = "GitHub OIDC role for read-only planning and encrypted plan publication"
  assume_role_policy   = data.aws_iam_policy_document.plan_assume.json
  max_session_duration = 3600
  tags                 = merge(local.common_tags, { Purpose = "terraform-plan" })
}

resource "aws_iam_role_policy_attachment" "plan_read_only" {
  role       = aws_iam_role.plan.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "plan_operations" {
  name   = "davdeploy-terraform-plan-operations"
  role   = aws_iam_role.plan.id
  policy = data.aws_iam_policy_document.plan_operations.json
}

data "aws_iam_policy_document" "plan_operations" {
  statement {
    sid       = "StateBucket"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [data.aws_s3_bucket.state.arn]
  }
  statement {
    sid       = "StateObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${data.aws_s3_bucket.state.arn}/serverless-control-plane/*"]
  }
  statement {
    sid       = "StateLock"
    effect    = "Allow"
    actions   = ["dynamodb:DescribeTable", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
    resources = [data.aws_dynamodb_table.lock.arn]
  }
  statement {
    sid       = "PublishSavedPlans"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [aws_s3_bucket.plans.arn]
  }
  statement {
    sid       = "PublishSavedPlanObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.plans.arn}/plans/serverless-control-plane/*"]
  }
  statement {
    sid       = "PublishReleaseObjects"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation", "s3:GetBucketVersioning", "s3:ListBucket"]
    resources = [aws_s3_bucket.releases.arn]
  }
  statement {
    sid       = "PublishReleaseObjectVersions"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"]
    resources = ["${aws_s3_bucket.releases.arn}/releases/serverless-control-plane/*"]
  }
  statement {
    sid       = "EncryptArtifacts"
    effect    = "Allow"
    actions   = ["kms:DescribeKey", "kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.plans.arn, aws_kms_key.releases.arn]
  }
}

resource "aws_iam_role" "apply" {
  name                 = "davdeploy-terraform-apply-github"
  description          = "GitHub OIDC role for applying only reviewed davdeploy saved plans"
  assume_role_policy   = data.aws_iam_policy_document.apply_assume.json
  max_session_duration = 3600
  tags                 = merge(local.common_tags, { Purpose = "terraform-apply" })
}

resource "aws_iam_role_policy_attachment" "apply_read_only" {
  role       = aws_iam_role.apply.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "apply_backend" {
  name   = "davdeploy-terraform-apply-backend"
  role   = aws_iam_role.apply.id
  policy = data.aws_iam_policy_document.apply_backend.json
}

data "aws_iam_policy_document" "apply_backend" {
  statement {
    sid       = "StateBucket"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [data.aws_s3_bucket.state.arn]
  }
  statement {
    sid       = "StateObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${data.aws_s3_bucket.state.arn}/serverless-control-plane/*"]
  }
  statement {
    sid       = "StateLock"
    effect    = "Allow"
    actions   = ["dynamodb:DescribeTable", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
    resources = [data.aws_dynamodb_table.lock.arn]
  }
  statement {
    sid       = "ReadSavedPlans"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [aws_s3_bucket.plans.arn]
  }
  statement {
    sid       = "ReadSavedPlanObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.plans.arn}/plans/serverless-control-plane/*"]
  }
  statement {
    sid       = "ReadReleaseObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${aws_s3_bucket.releases.arn}/releases/serverless-control-plane/*"]
  }
  statement {
    sid       = "DecryptArtifacts"
    effect    = "Allow"
    actions   = ["kms:DescribeKey", "kms:Decrypt"]
    resources = [aws_kms_key.plans.arn, aws_kms_key.releases.arn]
  }
}

resource "aws_iam_role_policy" "apply_control_plane" {
  name   = "davdeploy-serverless-control-plane"
  role   = aws_iam_role.apply.id
  policy = data.aws_iam_policy_document.apply_control_plane.json
}

data "aws_iam_policy_document" "apply_control_plane" {
  statement {
    sid       = "CreateDavDeployCognitoEmailKey"
    effect    = "Allow"
    actions   = ["kms:CreateKey"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/Product"
      values   = ["davdeploy"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/ManagedBy"
      values   = ["Terraform"]
    }
  }
  statement {
    sid    = "ManageDavDeployCognitoEmailKey"
    effect = "Allow"
    actions = [
      "kms:DescribeKey", "kms:GetKeyPolicy", "kms:PutKeyPolicy", "kms:ListResourceTags",
      "kms:TagResource", "kms:UntagResource", "kms:EnableKeyRotation", "kms:DisableKeyRotation",
      "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion", "kms:CreateGrant", "kms:RevokeGrant"
    ]
    resources = ["arn:${data.aws_partition.current.partition}:kms:${var.region}:${data.aws_caller_identity.current.account_id}:key/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Product"
      values   = ["davdeploy"]
    }
  }
  statement {
    sid    = "CustomerExecutorCreate"
    effect = "Allow"
    actions = [
      "codebuild:CreateProject"
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/Product"
      values   = ["davdeploy"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/ManagedBy"
      values   = ["Terraform"]
    }
  }
  statement {
    sid    = "CustomerExecutorLifecycle"
    effect = "Allow"
    actions = [
      "codebuild:UpdateProject",
      "codebuild:DeleteProject",
      "codebuild:TagResource",
      "codebuild:UntagResource"
    ]
    resources = ["arn:${data.aws_partition.current.partition}:codebuild:${var.region}:${data.aws_caller_identity.current.account_id}:project/davdeploy-customer-executor"]
  }
  statement {
    sid    = "Networking"
    effect = "Allow"
    actions = [
      "ec2:CreateVpc", "ec2:DeleteVpc", "ec2:ModifyVpcAttribute",
      "ec2:CreateSubnet", "ec2:DeleteSubnet", "ec2:ModifySubnetAttribute",
      "ec2:CreateSecurityGroup", "ec2:DeleteSecurityGroup",
      "ec2:AuthorizeSecurityGroupIngress", "ec2:AuthorizeSecurityGroupEgress",
      "ec2:RevokeSecurityGroupIngress", "ec2:RevokeSecurityGroupEgress",
      "ec2:CreateTags", "ec2:DeleteTags"
    ]
    resources = ["*"]
  }
  statement {
    sid    = "Database"
    effect = "Allow"
    actions = [
      "rds:AddTagsToResource", "rds:RemoveTagsFromResource",
      "rds:CreateDBCluster", "rds:ModifyDBCluster", "rds:DeleteDBCluster",
      "rds:CreateDBInstance", "rds:ModifyDBInstance", "rds:DeleteDBInstance",
      "rds:CreateDBSubnetGroup", "rds:ModifyDBSubnetGroup", "rds:DeleteDBSubnetGroup"
    ]
    resources = ["*"]
  }
  statement {
    sid    = "Runtime"
    effect = "Allow"
    actions = [
      "lambda:CreateFunction", "lambda:UpdateFunctionCode", "lambda:UpdateFunctionConfiguration",
      "lambda:DeleteFunction", "lambda:AddPermission", "lambda:RemovePermission", "lambda:TagResource", "lambda:UntagResource",
      "lambda:CreateEventSourceMapping", "lambda:UpdateEventSourceMapping", "lambda:DeleteEventSourceMapping"
    ]
    resources = ["arn:${data.aws_partition.current.partition}:lambda:${var.region}:${data.aws_caller_identity.current.account_id}:function:davdeploy-*"]
  }
  statement {
    sid       = "RuntimeEventSources"
    effect    = "Allow"
    actions   = ["lambda:CreateEventSourceMapping"]
    resources = ["*"]
  }
  statement {
    sid    = "Identity"
    effect = "Allow"
    actions = [
      "cognito-idp:CreateUserPool", "cognito-idp:UpdateUserPool", "cognito-idp:DeleteUserPool",
      "cognito-idp:CreateUserPoolClient", "cognito-idp:UpdateUserPoolClient", "cognito-idp:DeleteUserPoolClient",
      "cognito-idp:CreateUserPoolDomain", "cognito-idp:DeleteUserPoolDomain",
      "cognito-idp:SetUserPoolMfaConfig", "cognito-idp:TagResource", "cognito-idp:UntagResource"
    ]
    resources = ["*"]
  }
  statement {
    sid    = "ApiGateway"
    effect = "Allow"
    actions = [
      "apigateway:POST", "apigateway:PUT", "apigateway:PATCH", "apigateway:DELETE",
      "apigateway:TagResource", "apigateway:UntagResource"
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:apigateway:${var.region}::/apis*",
      "arn:${data.aws_partition.current.partition}:apigateway:${var.region}::/tags/arn%3Aaws%3Aapigateway%3A${var.region}%3A%3A%2Fv2%2Fapis%2F*"
    ]
  }
  statement {
    sid    = "RdsManagedMasterSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:CreateSecret", "secretsmanager:TagResource"
    ]
    resources = ["arn:${data.aws_partition.current.partition}:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:rds!cluster-*"]
  }
  statement {
    sid    = "Queues"
    effect = "Allow"
    actions = [
      "sqs:CreateQueue", "sqs:DeleteQueue", "sqs:SetQueueAttributes", "sqs:TagQueue", "sqs:UntagQueue"
    ]
    resources = ["arn:${data.aws_partition.current.partition}:sqs:${var.region}:${data.aws_caller_identity.current.account_id}:davdeploy-*"]
  }
  statement {
    sid    = "Schedules"
    effect = "Allow"
    actions = [
      "events:PutRule", "events:DeleteRule", "events:PutTargets", "events:RemoveTargets", "events:TagResource", "events:UntagResource"
    ]
    resources = ["arn:${data.aws_partition.current.partition}:events:${var.region}:${data.aws_caller_identity.current.account_id}:rule/davdeploy-*"]
  }
  statement {
    sid       = "Budgets"
    effect    = "Allow"
    actions   = ["budgets:CreateBudget", "budgets:ModifyBudget", "budgets:DeleteBudget"]
    resources = ["arn:${data.aws_partition.current.partition}:budgets::${data.aws_caller_identity.current.account_id}:budget/davdeploy-*"]
  }
  statement {
    sid    = "OperationalLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup", "logs:DeleteLogGroup", "logs:PutRetentionPolicy",
      "logs:DeleteRetentionPolicy", "logs:TagResource", "logs:UntagResource"
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/davdeploy-*",
      "arn:${data.aws_partition.current.partition}:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/davdeploy-*:*"
    ]
  }
  statement {
    sid    = "OperationalAlarms"
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricAlarm", "cloudwatch:DeleteAlarms",
      "cloudwatch:TagResource", "cloudwatch:UntagResource"
    ]
    resources = ["arn:${data.aws_partition.current.partition}:cloudwatch:${var.region}:${data.aws_caller_identity.current.account_id}:alarm:davdeploy-*"]
  }
  statement {
    sid    = "OperationalNotifications"
    effect = "Allow"
    actions = [
      "sns:CreateTopic", "sns:DeleteTopic", "sns:SetTopicAttributes",
      "sns:TagResource", "sns:UntagResource", "sns:Subscribe", "sns:Unsubscribe"
    ]
    resources = ["arn:${data.aws_partition.current.partition}:sns:${var.region}:${data.aws_caller_identity.current.account_id}:davdeploy-*"]
  }
  statement {
    sid    = "RuntimeRoles"
    effect = "Allow"
    actions = [
      "iam:CreateRole", "iam:DeleteRole", "iam:UpdateAssumeRolePolicy", "iam:TagRole", "iam:UntagRole",
      "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:PassRole"
    ]
    resources = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/davdeploy-*"]
  }
  statement {
    sid       = "RdsServiceRole"
    effect    = "Allow"
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["arn:${data.aws_partition.current.partition}:iam::*:role/aws-service-role/rds.amazonaws.com/AWSServiceRoleForRDS"]
    condition {
      test     = "StringEquals"
      variable = "iam:AWSServiceName"
      values   = ["rds.amazonaws.com"]
    }
  }
  statement {
    sid       = "CognitoEmailServiceRole"
    effect    = "Allow"
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/email.cognito-idp.amazonaws.com/AWSServiceRoleForAmazonCognitoIdpEmailService"]
    condition {
      test     = "StringEquals"
      variable = "iam:AWSServiceName"
      values   = ["email.cognito-idp.amazonaws.com"]
    }
  }
}
