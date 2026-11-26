data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
  project_service_id = substr(
    sha256("${var.connection_id}:${var.project_id}:${var.region}"),
    0,
    24,
  )
  service_name = "davdeploy-ecs-${local.project_service_id}"
  tags = {
    Project               = "davdeploy"
    ProjectId             = var.project_id
    ManagedBy             = "davdeploy"
    Scope                 = var.deployment_scope
    Placement             = "customer-sandbox"
    AccountBoundary       = "same-account-pilot"
    Cell                  = "customer-sandbox-1"
    Purpose               = "customer-ecs-express-create-validate-destroy"
    ConnectionId          = var.connection_id
    davdeployPlanDigest   = var.plan_digest
    davdeploySourceRepo   = var.source_repository
    davdeploySourceCommit = substr(var.source_commit, 0, 12)
  }
}

resource "terraform_data" "account_guard" {
  input = data.aws_caller_identity.current.account_id

  lifecycle {
    precondition {
      condition     = data.aws_caller_identity.current.account_id == var.expected_account_id
      error_message = "AWS account guard failed. This pilot may only run in the expected customer account."
    }

    precondition {
      condition     = data.aws_region.current.region == var.region
      error_message = "AWS Region guard failed. Re-run in the explicitly selected customer Region."
    }

    precondition {
      condition     = var.deployment_scope == "customer-sandbox" && var.customer_vpc_cidr != var.platform_vpc_cidr
      error_message = "Customer resources require the customer-sandbox scope and a VPC CIDR distinct from the platform VPC."
    }

    precondition {
      condition     = !var.enable_service || var.image_identifier != "placeholder.invalid/davdeploy-customer-workload:unset"
      error_message = "image_identifier must point to a pushed workload image before enabling the ECS Express service."
    }
  }
}

data "aws_iam_role" "execution" {
  name       = "davdeployEcsExpressTask-${var.connection_id}"
  depends_on = [terraform_data.account_guard]
}

data "aws_iam_role" "infrastructure" {
  name       = "davdeployEcsExpressInfra-${var.connection_id}"
  depends_on = [terraform_data.account_guard]
}

# Preserve any state created by the earlier pilot root. The new connection-
# scoped roles are provisioned separately; do not let this source revision
# destroy legacy project-scoped roles during state reconciliation.
removed {
  from = aws_iam_role.execution

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_iam_role.infrastructure

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_iam_role_policy_attachment.execution

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_iam_role_policy_attachment.infrastructure

  lifecycle {
    destroy = false
  }
}

resource "aws_vpc" "customer" {
  cidr_block           = var.customer_vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(local.tags, { Name = "${local.service_name}-vpc" })
}

resource "aws_internet_gateway" "customer" {
  vpc_id = aws_vpc.customer.id
  tags   = merge(local.tags, { Name = "${local.service_name}-igw" })
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.customer.id
  cidr_block              = cidrsubnet(var.customer_vpc_cidr, 8, count.index + 10)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true
  tags                    = merge(local.tags, { Name = "${local.service_name}-public-${count.index + 1}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.customer.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.customer.id
  }
  tags = merge(local.tags, { Name = "${local.service_name}-public" })
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_ecr_repository" "workload" {
  name                 = local.service_name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "workload" {
  name              = "/aws/ecs/${local.service_name}"
  retention_in_days = 3
  tags              = local.tags
}

resource "aws_ecs_express_gateway_service" "workload" {
  count                   = var.enable_service ? 1 : 0
  service_name            = local.service_name
  execution_role_arn      = data.aws_iam_role.execution.arn
  infrastructure_role_arn = data.aws_iam_role.infrastructure.arn
  cpu                     = "256"
  memory                  = "512"
  health_check_path       = "/healthz"
  wait_for_steady_state   = true
  tags                    = local.tags

  primary_container {
    image          = var.image_identifier
    container_port = 8000

    aws_logs_configuration {
      log_group         = aws_cloudwatch_log_group.workload.name
      log_stream_prefix = "customer-test"
    }

    environment {
      name  = "DAVDEPLOY_TEST_SCOPE"
      value = "same-account-customer-sandbox"
    }
  }

  network_configuration {
    subnets = aws_subnet.public[*].id
  }

  scaling_target {
    auto_scaling_metric       = "AVERAGE_CPU"
    auto_scaling_target_value = 70
    min_task_count            = 1
    max_task_count            = 1
  }

}
