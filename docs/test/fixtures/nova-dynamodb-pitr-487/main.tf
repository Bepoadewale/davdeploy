locals {
  table_name = "davdeploy-nova-dynamodb-pitr-487-${var.run_id}"
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-nova-dynamodb-pitr-recovery-test"
    TestId    = "nova-dynamodb-pitr-487-${var.run_id}"
  }
}

module "dynamodb_table" {
  source        = "../../../../infrastructure/terraform/modules/dynamodb-table"
  name          = local.table_name
  hash_key      = "pk"
  hash_key_type = "S"
  tags          = local.tags
}
