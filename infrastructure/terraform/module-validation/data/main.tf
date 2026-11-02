locals {
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

module "dynamodb" {
  source   = "../../modules/dynamodb-table"
  name     = "davdeploy-${var.test_id}"
  hash_key = "id"
  tags     = local.tags
}

output "table_arn" { value = module.dynamodb.arn }
