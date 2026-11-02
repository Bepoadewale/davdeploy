variable "test_id" { type = string }

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
}

output "cluster_name" { value = module.eks.cluster_name }
