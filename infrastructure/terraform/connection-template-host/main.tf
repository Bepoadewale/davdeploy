locals {
  template_source = "${path.module}/../../cloudformation/customer-discovery-role.yaml"
  template_hash   = filesha256(local.template_source)
  template_key    = "cloudformation/customer-discovery-role-${local.template_hash}.yaml"
  tags = {
    Project   = "davdeploy"
    ManagedBy = "terraform"
    Purpose   = "public-cloudformation-template-only"
  }
}

resource "aws_s3_bucket" "templates" {
  bucket = var.bucket_name
  tags   = local.tags
}

resource "aws_s3_bucket_ownership_controls" "templates" {
  bucket = aws_s3_bucket.templates.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "templates" {
  bucket = aws_s3_bucket.templates.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "templates" {
  bucket = aws_s3_bucket.templates.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "templates" {
  bucket                  = aws_s3_bucket.templates.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = false
  restrict_public_buckets = false
}

data "aws_iam_policy_document" "public_template_only" {
  statement {
    sid       = "PublicReadOnlyForVersionedCloudFormationTemplates"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.templates.arn}/cloudformation/*"]
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
  }
}

resource "aws_s3_bucket_policy" "templates" {
  bucket     = aws_s3_bucket.templates.id
  policy     = data.aws_iam_policy_document.public_template_only.json
  depends_on = [aws_s3_bucket_public_access_block.templates]
}

resource "aws_s3_object" "active_customer_discovery_role" {
  bucket       = aws_s3_bucket.templates.id
  key          = local.template_key
  source       = local.template_source
  etag         = filemd5(local.template_source)
  content_type = "application/x-yaml"
  tags         = local.tags
  depends_on = [
    aws_s3_bucket_ownership_controls.templates,
    aws_s3_bucket_server_side_encryption_configuration.templates,
    aws_s3_bucket_versioning.templates,
  ]
}

# Preserve previously published immutable template objects. A customer may
# still have an active CloudFormation stack or saved Quick Create URL pointing
# at one of these keys, so replacing the current template must never delete it.
resource "aws_s3_object" "retained_customer_templates" {
  for_each = var.retained_template_keys

  bucket = aws_s3_bucket.templates.id
  key    = each.value

  lifecycle {
    prevent_destroy = true
    ignore_changes  = all
  }
}

# Retain the former managed object when the first administrator-pilot-aware
# template is superseded. Future template revisions append their former key to
# `retained_template_keys` before publication.
moved {
  from = aws_s3_object.customer_discovery_role
  to   = aws_s3_object.retained_customer_templates["cloudformation/customer-discovery-role-600858c0ab944fd3f5aef06626ec5bc6ef9ed46352b418d87d651e05196bc11d.yaml"]
}
