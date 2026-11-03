data "aws_region" "current" {}

locals {
  name = "davdeploy-${var.test_id}"
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

resource "aws_s3_bucket" "artifacts" {
  bucket        = "${local.name}-artifacts"
  force_destroy = true
  tags          = local.tags
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "endpoint" {
  name               = "${local.name}-endpoint"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "endpoint" {
  statement {
    sid       = "ReadOnlyDisposableModelArtifact"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/model/*"]
  }

  statement {
    sid       = "AuthorizeManagedXgboostImage"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "PullManagedXgboostImage"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [
      "arn:aws:ecr:${data.aws_region.current.name}:683313688378:repository/sagemaker-xgboost",
    ]
  }
}

resource "aws_iam_role_policy" "endpoint" {
  name   = "${local.name}-endpoint"
  role   = aws_iam_role.endpoint.id
  policy = data.aws_iam_policy_document.endpoint.json
}

module "endpoint" {
  source             = "../../modules/sagemaker-endpoint"
  name               = local.name
  execution_role_arn = aws_iam_role.endpoint.arn
  image_uri          = "683313688378.dkr.ecr.${data.aws_region.current.name}.amazonaws.com/sagemaker-xgboost:1.7-1"
  model_data_url     = var.model_data_url
  instance_type      = "ml.m5.large"
  tags               = local.tags

  depends_on = [
    aws_iam_role_policy.endpoint,
    aws_s3_bucket_public_access_block.artifacts,
    aws_s3_bucket_server_side_encryption_configuration.artifacts,
  ]
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "endpoint_name" {
  value = module.endpoint.endpoint_name
}
