data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs                     = slice(data.aws_availability_zones.available.names, 0, 2)
  service_name            = var.service_name != "" ? var.service_name : "davdeploy-${var.connection_id}-workload"
  app_runner_service_name = var.app_runner_service_name != "" ? var.app_runner_service_name : local.service_name
  ecr_repository_name     = var.ecr_repository_name != "" ? var.ecr_repository_name : "davdeploy-${var.connection_id}-workload"
  tags = {
    Project               = "davdeploy"
    ManagedBy             = "davdeploy"
    Scope                 = var.deployment_scope
    Placement             = "customer-sandbox"
    AccountBoundary       = "same-account-pilot"
    Cell                  = "customer-sandbox-1"
    Purpose               = "real-app-runner-create-validate-destroy"
    ConnectionId          = var.connection_id
    davdeployPlanDigest   = var.plan_digest
    davdeploySourceRepo   = "Bepoadewale/ai-platform-control-plane"
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
      condition     = data.aws_region.current.name == var.region
      error_message = "AWS region guard failed. Re-run in the explicitly selected customer region."
    }

    precondition {
      condition     = var.deployment_scope == "customer-sandbox" && var.customer_vpc_cidr != var.platform_vpc_cidr
      error_message = "Customer resources require the customer-sandbox scope and a VPC CIDR distinct from the platform VPC."
    }

    precondition {
      condition     = !var.enable_service || var.image_identifier != "placeholder.invalid/davdeploy-customer-workload:unset"
      error_message = "image_identifier must be set before enabling the App Runner service."
    }
  }
}

resource "aws_vpc" "customer_sandbox" {
  cidr_block           = var.customer_vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.tags, { Name = "davdeploy-customer-sandbox-vpc" })

  depends_on = [terraform_data.account_guard]
}

resource "aws_subnet" "customer_private" {
  count             = 2
  vpc_id            = aws_vpc.customer_sandbox.id
  cidr_block        = cidrsubnet(var.customer_vpc_cidr, 8, count.index + 10)
  availability_zone = local.azs[count.index]

  tags = merge(local.tags, { Name = "davdeploy-customer-sandbox-private-${count.index + 1}" })
}

resource "aws_internet_gateway" "customer_sandbox" {
  vpc_id = aws_vpc.customer_sandbox.id
  tags   = merge(local.tags, { Name = "davdeploy-customer-sandbox-igw" })
}

resource "aws_subnet" "customer_nat" {
  vpc_id                  = aws_vpc.customer_sandbox.id
  cidr_block              = cidrsubnet(var.customer_vpc_cidr, 8, 20)
  availability_zone       = local.azs[0]
  map_public_ip_on_launch = true
  tags                    = merge(local.tags, { Name = "davdeploy-customer-sandbox-nat" })
}

resource "aws_route_table" "customer_public" {
  vpc_id = aws_vpc.customer_sandbox.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.customer_sandbox.id
  }
  tags = merge(local.tags, { Name = "davdeploy-customer-sandbox-public" })
}

resource "aws_route_table_association" "customer_nat" {
  subnet_id      = aws_subnet.customer_nat.id
  route_table_id = aws_route_table.customer_public.id
}

resource "aws_eip" "customer_nat" {
  domain = "vpc"
  tags   = merge(local.tags, { Name = "davdeploy-customer-sandbox-nat" })
}

resource "aws_nat_gateway" "customer_sandbox" {
  allocation_id = aws_eip.customer_nat.id
  subnet_id     = aws_subnet.customer_nat.id
  tags          = merge(local.tags, { Name = "davdeploy-customer-sandbox-nat" })
  depends_on    = [aws_internet_gateway.customer_sandbox]
}

resource "aws_route_table" "customer_private" {
  vpc_id = aws_vpc.customer_sandbox.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.customer_sandbox.id
  }
  tags = merge(local.tags, { Name = "davdeploy-customer-sandbox-private" })
}

resource "aws_route_table_association" "customer_private" {
  count          = length(aws_subnet.customer_private)
  subnet_id      = aws_subnet.customer_private[count.index].id
  route_table_id = aws_route_table.customer_private.id
}

resource "aws_security_group" "customer_runtime" {
  name        = "davdeploy-customer-sandbox-runtime"
  description = "No-default-egress boundary for the customer sandbox App Runner workload."
  vpc_id      = aws_vpc.customer_sandbox.id

  tags = merge(local.tags, { Name = "davdeploy-customer-sandbox-runtime" })
}

resource "aws_vpc_security_group_egress_rule" "customer_runtime_https" {
  security_group_id = aws_security_group.customer_runtime.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  description       = "HTTPS-only egress through the customer sandbox NAT gateway."
}

resource "aws_apprunner_vpc_connector" "customer_sandbox" {
  vpc_connector_name = "davdeploy-customer-sandbox"
  subnets            = aws_subnet.customer_private[*].id
  security_groups    = [aws_security_group.customer_runtime.id]
  tags               = local.tags
}

resource "aws_ecr_repository" "customer_workload" {
  name                 = local.ecr_repository_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "customer_workload" {
  name              = "/aws/apprunner/${local.service_name}"
  retention_in_days = 3
  tags              = local.tags
}

resource "aws_apprunner_service" "customer_workload" {
  count        = var.enable_service ? 1 : 0
  service_name = local.app_runner_service_name
  tags         = local.tags

  source_configuration {
    auto_deployments_enabled = false

    authentication_configuration {
      access_role_arn = var.app_runner_ecr_access_role_arn
    }

    image_repository {
      image_identifier      = var.image_identifier
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"
        runtime_environment_variables = {
          PLATFORM_AUTH_MODE              = "headers"
          PLATFORM_ALLOW_INSECURE_HEADERS = "true"
          PLATFORM_OPA_DECISION_URL       = "fixture-disabled-for-healthz-only"
          PLATFORM_CONTROL_PLANE_DB       = "/app/state/control-plane.db"
          DAVDEPLOY_PLAN_DIGEST           = var.plan_digest
          DAVDEPLOY_SOURCE_REPO           = var.source_repository
          DAVDEPLOY_SOURCE_COMMIT         = var.source_commit
        }
      }
    }
  }

  instance_configuration {
    cpu               = var.cpu
    memory            = var.memory
    instance_role_arn = var.app_runner_runtime_role_arn
  }

  network_configuration {
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.customer_sandbox.arn
    }
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/healthz"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  depends_on = [
    terraform_data.account_guard,
    aws_cloudwatch_log_group.customer_workload,
    aws_apprunner_vpc_connector.customer_sandbox,
  ]
}
