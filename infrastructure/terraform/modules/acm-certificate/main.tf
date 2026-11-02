variable "domain_name" { type = string }
variable "tags" { type = map(string) }

resource "aws_acm_certificate" "this" {
  domain_name       = var.domain_name
  validation_method = "DNS"
  tags              = var.tags
}

output "arn" { value = aws_acm_certificate.this.arn }
output "validation_records" { value = aws_acm_certificate.this.domain_validation_options }
