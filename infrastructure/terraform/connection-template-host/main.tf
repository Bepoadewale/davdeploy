locals {
  template_source = "${path.module}/../../cloudformation/customer-discovery-role.yaml"
  template_hash   = filesha256(local.template_source)
  template_key    = "cloudformation/customer-discovery-role-${local.template_hash}.yaml"
  published_keys  = setunion(var.retained_template_keys, toset([local.template_key]))
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

# One instance per immutable content-hash key gives each object a stable state
# address. The current source is uploaded only at its matching hash key; older
# instances stay represented by key in retained_template_keys.
resource "aws_s3_object" "published_customer_templates" {
  for_each = local.published_keys

  bucket = aws_s3_bucket.templates.id
  key    = each.key

  source       = each.key == local.template_key ? local.template_source : null
  etag         = each.key == local.template_key ? filemd5(local.template_source) : null
  content_type = "application/x-yaml"
  tags         = local.tags

  depends_on = [
    aws_s3_bucket_ownership_controls.templates,
    aws_s3_bucket_server_side_encryption_configuration.templates,
    aws_s3_bucket_versioning.templates,
  ]

  lifecycle {
    prevent_destroy = true
    ignore_changes  = all
  }
}

# Migrate existing Terraform addresses without changing their S3 keys. Every
# template now uses the same protected, key-derived address from publication.
moved {
  from = aws_s3_object.current_customer_discovery_role
  to   = aws_s3_object.published_customer_templates["cloudformation/customer-discovery-role-8c5d1c82682b3bb90ff1f45d121b475e7b33b484f556feabafbf387c335aea4e.yaml"]
}

moved {
  from = aws_s3_object.customer_discovery_role
  to   = aws_s3_object.published_customer_templates["cloudformation/customer-discovery-role-600858c0ab944fd3f5aef06626ec5bc6ef9ed46352b418d87d651e05196bc11d.yaml"]
}

moved {
  from = aws_s3_object.active_customer_discovery_role
  to   = aws_s3_object.published_customer_templates["cloudformation/customer-discovery-role-7e03683a397f0d4e2a5f68b9559d2790ff127e5513540457b47e9c4779b2b793.yaml"]
}

moved {
  from = aws_s3_object.published_customer_discovery_role
  to   = aws_s3_object.published_customer_templates["cloudformation/customer-discovery-role-f3d9e1e5776fe147bbbc10107e41d221497f9b98c6b641eb8ac08467fd54aedb.yaml"]
}

moved {
  from = aws_s3_object.retained_customer_templates["cloudformation/customer-discovery-role-600858c0ab944fd3f5aef06626ec5bc6ef9ed46352b418d87d651e05196bc11d.yaml"]
  to   = aws_s3_object.published_customer_templates["cloudformation/customer-discovery-role-600858c0ab944fd3f5aef06626ec5bc6ef9ed46352b418d87d651e05196bc11d.yaml"]
}

moved {
  from = aws_s3_object.retained_customer_templates["cloudformation/customer-discovery-role-7e03683a397f0d4e2a5f68b9559d2790ff127e5513540457b47e9c4779b2b793.yaml"]
  to   = aws_s3_object.published_customer_templates["cloudformation/customer-discovery-role-7e03683a397f0d4e2a5f68b9559d2790ff127e5513540457b47e9c4779b2b793.yaml"]
}

moved {
  from = aws_s3_object.retained_customer_templates["cloudformation/customer-discovery-role-f3d9e1e5776fe147bbbc10107e41d221497f9b98c6b641eb8ac08467fd54aedb.yaml"]
  to   = aws_s3_object.published_customer_templates["cloudformation/customer-discovery-role-f3d9e1e5776fe147bbbc10107e41d221497f9b98c6b641eb8ac08467fd54aedb.yaml"]
}
