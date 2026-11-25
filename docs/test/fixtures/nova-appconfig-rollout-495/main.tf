data "aws_caller_identity" "current" {}

locals {
  name = "davdeploy-nova-ff-495-${var.test_id}"
  tags = {
    Product   = "davdeploy"
    ManagedBy = "davdeploy"
    Purpose   = "temporary-appconfig-feature-flag-validation"
    TestId    = var.test_id
  }
}

module "feature_flags" {
  source       = "../../../../infrastructure/terraform/modules/feature-flags"
  name         = local.name
  tags         = local.tags
  flag_name    = "nova_demo"
  flag_enabled = var.flag_enabled
}
