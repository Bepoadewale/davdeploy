variable "test_id" { type = string }

module "delivery" {
  source             = "../../modules/cloudfront-delivery"
  name               = "davdeploy-${var.test_id}"
  origin_domain_name = "www.example.com"
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

output "domain_name" { value = module.delivery.domain_name }
