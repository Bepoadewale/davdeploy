locals {
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-nova-s3-artifacts-module-test"
    TestId    = "nova-s3-artifacts-491-${var.run_id}"
  }
}

module "artifacts" {
  source = "../../../../infrastructure/terraform/modules/artifacts"

  name = var.bucket_name
  tags = local.tags
}
