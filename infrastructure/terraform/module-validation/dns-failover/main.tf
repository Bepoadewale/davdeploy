variable "test_id" { type = string }

locals {
  label = replace(var.test_id, "-", "")
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

module "zone" {
  source = "../../modules/dns-zone"
  name   = "${local.label}.validation.invalid"
  tags   = local.tags
}

module "failover" {
  source             = "../../modules/multi-region-dns"
  zone_id            = module.zone.zone_id
  name               = "app.${local.label}.validation.invalid"
  primary_endpoint   = "www.example.com"
  secondary_endpoint = "www.iana.org"
  tags               = local.tags
}

output "zone_id" { value = module.zone.zone_id }
