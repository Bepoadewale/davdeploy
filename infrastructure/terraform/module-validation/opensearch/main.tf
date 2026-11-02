variable "test_id" { type = string }

data "aws_vpc" "default" { default = true }
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

locals {
  tags = { ManagedBy = "terraform", Purpose = "davdeploy-module-validation", TestId = var.test_id }
}

resource "aws_security_group" "application" {
  name        = "davdeploy-${var.test_id}-application"
  description = "Disposable OpenSearch validation caller group."
  vpc_id      = data.aws_vpc.default.id
  tags        = local.tags
}

module "search" {
  source                         = "../../modules/opensearch"
  name                           = "dd${replace(var.test_id, "-", "")}"
  subnet_ids                     = data.aws_subnets.default.ids
  vpc_id                         = data.aws_vpc.default.id
  application_security_group_ids = [aws_security_group.application.id]
  tags                           = local.tags
}

output "endpoint" { value = module.search.endpoint }
