variable "test_id" { type = string }

locals {
  bucket_name = "davdeploy-${var.test_id}-origin"
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

resource "aws_s3_bucket" "origin" {
  bucket        = local.bucket_name
  force_destroy = true
  tags          = local.tags
}

resource "aws_s3_bucket_public_access_block" "origin" {
  bucket                  = aws_s3_bucket.origin.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

data "aws_iam_policy_document" "origin_read" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.origin.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
  }
}

resource "aws_s3_bucket_policy" "origin_read" {
  bucket     = aws_s3_bucket.origin.id
  policy     = data.aws_iam_policy_document.origin_read.json
  depends_on = [aws_s3_bucket_public_access_block.origin]
}

resource "aws_s3_bucket_website_configuration" "origin" {
  bucket = aws_s3_bucket.origin.id
  index_document { suffix = "index.html" }
}

resource "aws_s3_object" "index" {
  bucket       = aws_s3_bucket.origin.id
  key          = "index.html"
  content      = "<html><body>davdeploy-cloudfront-certification</body></html>"
  content_type = "text/html"
  etag         = md5("davdeploy-cloudfront-certification")
}

module "delivery" {
  source                 = "../../modules/cloudfront-delivery"
  name                   = "davdeploy-${var.test_id}"
  origin_domain_name     = aws_s3_bucket_website_configuration.origin.website_endpoint
  origin_protocol_policy = "http-only"
  tags                   = local.tags
  depends_on             = [aws_s3_object.index, aws_s3_bucket_policy.origin_read]
}

output "domain_name" { value = module.delivery.domain_name }
