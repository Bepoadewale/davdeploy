data "aws_vpc" "default" { default = true }

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

locals {
  name       = "davdeploy-${var.test_id}"
  subnet_ids = slice(data.aws_subnets.default.ids, 0, 2)
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

resource "aws_security_group" "application" {
  name        = "${local.name}-application"
  description = "Disposable test application group without ingress."
  vpc_id      = data.aws_vpc.default.id
  tags        = local.tags
}

module "efs" {
  source                         = "../../modules/efs-shared-storage"
  name                           = "${local.name}-efs"
  subnet_ids                     = local.subnet_ids
  vpc_id                         = data.aws_vpc.default.id
  application_security_group_ids = [aws_security_group.application.id]
  tags                           = local.tags
}

module "redis" {
  source                         = "../../modules/elasticache-redis"
  name                           = "${local.name}-redis"
  subnet_ids                     = local.subnet_ids
  vpc_id                         = data.aws_vpc.default.id
  application_security_group_ids = [aws_security_group.application.id]
  tags                           = local.tags
}

module "aurora" {
  source                         = "../../modules/aurora-postgres"
  name                           = "${local.name}-aurora"
  subnet_ids                     = local.subnet_ids
  vpc_id                         = data.aws_vpc.default.id
  application_security_group_ids = [aws_security_group.application.id]
  deletion_protection            = false
  skip_final_snapshot            = true
  tags                           = local.tags
}

output "aurora_cluster_arn" { value = module.aurora.cluster_arn }
output "efs_id" { value = module.efs.file_system_id }
output "redis_endpoint" { value = module.redis.primary_endpoint }
