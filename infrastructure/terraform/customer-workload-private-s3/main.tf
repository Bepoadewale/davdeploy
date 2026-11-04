data "aws_caller_identity" "current" {}

locals {
  project_scope = "${var.connection_id}:${var.project_id}:${var.region}"
  project_hash  = substr(sha256(local.project_scope), 0, 20)
  bucket_name   = "davdeploy-${var.expected_account_id}-${var.region}-${local.project_hash}"

  tags = {
    ManagedBy           = "davdeploy"
    DavDeployConnection = var.connection_id
    DavDeployProject    = var.project_id
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

resource "aws_s3_bucket" "private" {
  bucket        = local.bucket_name
  force_destroy = false
  tags          = local.tags
  depends_on    = [terraform_data.account_guard]
}

resource "aws_s3_bucket_ownership_controls" "private" {
  bucket = aws_s3_bucket.private.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "private" {
  bucket                  = aws_s3_bucket.private.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "private" {
  bucket = aws_s3_bucket.private.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "private" {
  bucket = aws_s3_bucket.private.id
  versioning_configuration {
    status = "Enabled"
  }
}

data "aws_iam_policy_document" "tls_only" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.private.arn, "${aws_s3_bucket.private.arn}/*"]
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

resource "aws_s3_bucket_policy" "tls_only" {
  bucket = aws_s3_bucket.private.id
  policy = data.aws_iam_policy_document.tls_only.json

  depends_on = [
    aws_s3_bucket_public_access_block.private,
    aws_s3_bucket_ownership_controls.private,
  ]
}

output "bucket_name" {
  value = aws_s3_bucket.private.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.private.arn
}
