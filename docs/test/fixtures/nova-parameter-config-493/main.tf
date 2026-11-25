module "parameter" {
  source = "../../../../infrastructure/terraform/modules/parameter-config"

  name   = local.parameter_name
  value  = var.parameter_value
  key_id = "alias/aws/ssm"
  tags = {
    ManagedBy = "terraform"
    Product   = "davdeploy"
    Purpose   = "nova-parameter-config-493-test"
    TestId    = var.test_id
  }
}

locals {
  parameter_name = "/davdeploy/nova-parameter-config-493/${var.test_id}/synthetic"
}

output "parameter_arn" {
  value = module.parameter.arn
}
