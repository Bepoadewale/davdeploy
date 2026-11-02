variable "test_id" { type = string }
variable "operator_cidr" { type = string }

locals {
  name = "davdeploy-${var.test_id}"
  tags = { ManagedBy = "terraform", Purpose = "davdeploy-module-validation", TestId = var.test_id }
}

data "aws_availability_zones" "available" { state = "available" }

module "vpc" {
  source = "../../modules/vpc"
  name   = local.name
  cidr   = "10.251.0.0/20"
  azs    = slice(data.aws_availability_zones.available.names, 0, 2)
  tags   = local.tags
}

module "eks" {
  source     = "../../modules/eks"
  name       = local.name
  subnet_ids = module.vpc.private_subnet_ids
  tags       = local.tags
  # The production module defaults to private-only. This disposable test opens
  # the Kubernetes API only to the operator's single current address so a real
  # workload can be applied and observed.
  endpoint_public_access = true
  public_access_cidrs    = [var.operator_cidr]
}

output "cluster_name" { value = module.eks.cluster_name }
output "endpoint" { value = module.eks.endpoint }
