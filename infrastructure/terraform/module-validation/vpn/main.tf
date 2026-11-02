variable "test_id" { type = string }

locals {
  tags = { ManagedBy = "terraform", Purpose = "davdeploy-module-validation", TestId = var.test_id }
}

data "aws_vpc" "default" { default = true }

module "vpn" {
  source = "../../modules/site-to-site-vpn"
  name   = "davdeploy-${var.test_id}"
  vpc_id = data.aws_vpc.default.id
  # TEST-NET-2 is reserved for documentation and never represents a customer gateway.
  customer_gateway_ip = "198.51.100.10"
  static_routes_only  = true
  tags                = local.tags
}

output "vpn_connection_id" { value = module.vpn.vpn_connection_id }
