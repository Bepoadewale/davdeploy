data "aws_caller_identity" "current" {}

locals {
  zone_name = "${var.test_id}.cert.davdeploy.tech"
  base_name = "davdeploy-${var.test_id}-${data.aws_caller_identity.current.account_id}"
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

module "zone" {
  source = "../../modules/dns-zone"
  name   = local.zone_name
  tags   = local.tags
}

resource "aws_s3_bucket" "primary" {
  bucket        = "${local.base_name}-primary"
  force_destroy = true
  tags          = local.tags
}

resource "aws_s3_bucket" "secondary" {
  provider      = aws.secondary
  bucket        = "${local.base_name}-secondary"
  force_destroy = true
  tags          = local.tags
}

resource "aws_s3_bucket_public_access_block" "primary" {
  bucket                  = aws_s3_bucket.primary.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_public_access_block" "secondary" {
  provider                = aws.secondary
  bucket                  = aws_s3_bucket.secondary.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_website_configuration" "primary" {
  bucket = aws_s3_bucket.primary.id
  index_document { suffix = "health" }
}

resource "aws_s3_bucket_website_configuration" "secondary" {
  provider = aws.secondary
  bucket   = aws_s3_bucket.secondary.id
  index_document { suffix = "health" }
}

resource "aws_s3_object" "primary_health" {
  bucket       = aws_s3_bucket.primary.id
  key          = "health"
  content      = "primary-healthy"
  content_type = "text/plain"
}

resource "aws_s3_object" "secondary_health" {
  provider     = aws.secondary
  bucket       = aws_s3_bucket.secondary.id
  key          = "health"
  content      = "secondary-healthy"
  content_type = "text/plain"
}

resource "aws_s3_bucket_policy" "primary" {
  bucket     = aws_s3_bucket.primary.id
  policy     = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = "*", Action = "s3:GetObject", Resource = "${aws_s3_bucket.primary.arn}/*" }] })
  depends_on = [aws_s3_bucket_public_access_block.primary]
}

resource "aws_s3_bucket_policy" "secondary" {
  provider   = aws.secondary
  bucket     = aws_s3_bucket.secondary.id
  policy     = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = "*", Action = "s3:GetObject", Resource = "${aws_s3_bucket.secondary.arn}/*" }] })
  depends_on = [aws_s3_bucket_public_access_block.secondary]
}

module "failover" {
  source             = "../../modules/multi-region-dns"
  zone_id            = module.zone.zone_id
  name               = "app.${local.zone_name}"
  primary_endpoint   = aws_s3_bucket_website_configuration.primary.website_endpoint
  secondary_endpoint = aws_s3_bucket_website_configuration.secondary.website_endpoint
  health_check_type  = "HTTP"
  health_check_port  = 80
  health_check_path  = "/health"
  tags               = local.tags
  depends_on         = [aws_s3_object.primary_health, aws_s3_object.secondary_health, aws_s3_bucket_policy.primary, aws_s3_bucket_policy.secondary]
}

output "zone_name" { value = local.zone_name }
output "zone_name_servers" { value = module.zone.name_servers }
output "application_name" { value = "app.${local.zone_name}" }
