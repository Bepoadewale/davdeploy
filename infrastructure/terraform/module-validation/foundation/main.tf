data "aws_caller_identity" "current" {}

locals {
  name = "davdeploy-module-test-${var.test_id}"
  tags = {
    Project = "davdeploy"
    ManagedBy = "davdeploy"
    Purpose = "temporary-module-validation"
    TestId = var.test_id
  }
}

module "kms" {
  source = "../../modules/kms-key"
  name   = local.name
  tags   = local.tags
}

module "parameter" {
  source = "../../modules/parameter-config"
  name   = "/davdeploy/module-validation/${var.test_id}/configuration"
  value  = "validated"
  key_id = module.kms.key_arn
  tags   = local.tags
}

module "flags" {
  source = "../../modules/feature-flags"
  name   = local.name
  tags   = local.tags
}
