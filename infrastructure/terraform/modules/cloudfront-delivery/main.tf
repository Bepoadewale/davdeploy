variable "name" { type = string }
variable "origin_domain_name" { type = string }
variable "origin_protocol_policy" {
  type        = string
  description = "Use https-only for a custom origin; use http-only only with an S3 website endpoint."
  default     = "https-only"
  validation {
    condition     = contains(["http-only", "https-only", "match-viewer"], var.origin_protocol_policy)
    error_message = "origin_protocol_policy must be http-only, https-only, or match-viewer."
  }
}
variable "tags" { type = map(string) }

resource "aws_cloudfront_distribution" "this" {
  enabled             = true
  comment             = "DavDeploy ${var.name}"
  default_root_object = "index.html"

  origin {
    domain_name = var.origin_domain_name
    origin_id   = var.name
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = var.origin_protocol_policy
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = var.name
    viewer_protocol_policy = "redirect-to-https"
    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
  tags = var.tags
}

output "domain_name" { value = aws_cloudfront_distribution.this.domain_name }
