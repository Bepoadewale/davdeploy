variable "test_id" { type = string }

locals {
  domain = "${var.test_id}.cert.davdeploy.tech"
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

module "certificate" {
  source      = "../../modules/acm-certificate"
  domain_name = local.domain
  tags        = local.tags
}

module "email" {
  source = "../../modules/ses-email"
  domain = local.domain
  tags   = local.tags
}

output "domain" { value = local.domain }
output "acm_validation_records" { value = module.certificate.validation_records }
output "ses_verification_token" { value = module.email.verification_token }
output "ses_dkim_tokens" { value = module.email.dkim_tokens }
