variable "test_id" {
  type        = string
  description = "Unique lowercase identifier for this disposable validation stack."
  validation {
    condition     = can(regex("^batch-private-endpoints-517-[a-z0-9]+$", var.test_id))
    error_message = "test_id must start with batch-private-endpoints-517- and use lowercase letters and digits."
  }
}

variable "expires_at" {
  type        = string
  description = "UTC expiry timestamp tag for this one-hour disposable environment."
  validation {
    condition     = can(formatdate("YYYY-MM-DD'T'hh:mm:ss'Z'", var.expires_at))
    error_message = "expires_at must be a valid UTC timestamp."
  }
}

variable "region" {
  type        = string
  description = "AWS region for the disposable validation stack."
  default     = "us-east-1"
}

variable "availability_zones" {
  type        = list(string)
  description = "Two distinct enabled Availability Zones in region."
  default     = ["us-east-1a", "us-east-1b"]
  validation {
    condition     = length(var.availability_zones) == 2 && length(toset(var.availability_zones)) == 2
    error_message = "Exactly two distinct Availability Zones are required."
  }
}

variable "image_digest" {
  type        = string
  description = "SHA256 digest for the validation image pushed to the test ECR repository."
  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.image_digest))
    error_message = "image_digest must be a sha256 digest."
  }
}

terraform {
  required_version = ">= 1.6.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = local.tags
  }
}

data "aws_caller_identity" "current" {}

locals {
  name = "davdeploy-${var.test_id}"
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-private-batch-endpoints-517"
    TestId    = var.test_id
    ExpiresAt = var.expires_at
  }
  interface_services = toset(["ecr.api", "ecr.dkr", "logs"])
}

module "network" {
  source = "../../modules/vpc"
  name   = local.name
  cidr   = "10.241.0.0/16"
  azs    = var.availability_zones
  tags   = local.tags
}

module "ecr" {
  source = "../../modules/ecr"
  name   = local.name
  tags   = local.tags
}

data "aws_iam_policy_document" "batch_service_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["batch.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "batch_service" {
  name               = "${local.name}-service"
  assume_role_policy = data.aws_iam_policy_document.batch_service_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "batch_service" {
  role       = aws_iam_role.batch_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

resource "aws_iam_role" "task_execution" {
  name               = "${local.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_security_group" "batch" {
  name        = "${local.name}-batch"
  description = "Private Batch test task egress to required AWS endpoints only."
  vpc_id      = module.network.vpc_id
  egress      = []
  tags        = local.tags
}

resource "aws_security_group" "endpoints" {
  name        = "${local.name}-endpoints"
  description = "HTTPS ingress from the test Batch security group."
  vpc_id      = module.network.vpc_id
  egress      = []
  tags        = local.tags
}

resource "aws_vpc_security_group_egress_rule" "batch_to_interface_endpoints" {
  security_group_id            = aws_security_group.batch.id
  referenced_security_group_id = aws_security_group.endpoints.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  description                  = "HTTPS to private ECR and CloudWatch Logs endpoints."
  tags                         = local.tags
}

resource "aws_vpc_security_group_egress_rule" "batch_to_s3" {
  security_group_id = aws_security_group.batch.id
  prefix_list_id    = aws_vpc_endpoint.s3.prefix_list_id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  description       = "HTTPS to S3 image-layer storage through the gateway endpoint."
  tags              = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "endpoint_from_batch" {
  security_group_id            = aws_security_group.endpoints.id
  referenced_security_group_id = aws_security_group.batch.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  description                  = "HTTPS only from the Batch test tasks."
  tags                         = local.tags
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = local.interface_services
  vpc_id              = module.network.vpc_id
  service_name        = "com.amazonaws.${var.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  ip_address_type     = "ipv4"
  subnet_ids          = module.network.private_subnet_ids
  security_group_ids  = [aws_security_group.endpoints.id]
  tags                = merge(local.tags, { Name = "${local.name}-${replace(each.key, ".", "-")}" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.network.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  ip_address_type   = "ipv4"
  route_table_ids   = [module.network.private_route_table_id]
  tags              = merge(local.tags, { Name = "${local.name}-s3" })
}

resource "aws_cloudwatch_log_group" "batch" {
  name              = "/davdeploy/${var.test_id}/batch"
  retention_in_days = 1
  tags              = local.tags
}

module "batch" {
  source             = "../../modules/batch-compute"
  name               = local.name
  service_role_arn   = aws_iam_role.batch_service.arn
  instance_role_arn  = aws_iam_role.task_execution.arn
  subnet_ids         = module.network.private_subnet_ids
  security_group_ids = [aws_security_group.batch.id]
  image              = "${module.ecr.repository_url}@${var.image_digest}"
  log_group_name     = aws_cloudwatch_log_group.batch.name
  region             = var.region
  tags               = local.tags
  assign_public_ip   = false
  retry_attempts     = 1
  timeout_seconds    = 300
  max_vcpus          = 1
  depends_on         = [aws_iam_role_policy_attachment.batch_service, aws_iam_role_policy_attachment.task_execution]
}

output "account_id" { value = data.aws_caller_identity.current.account_id }
output "batch_job_definition_arn" { value = module.batch.job_definition_arn }
output "batch_job_definition_name" { value = local.name }
output "batch_job_queue_name" { value = local.name }
output "image_repository_url" { value = module.ecr.repository_url }
output "interface_endpoint_ids" { value = { for service, endpoint in aws_vpc_endpoint.interface : service => endpoint.id } }
output "log_group_name" { value = aws_cloudwatch_log_group.batch.name }
output "nat_gateway_id" { value = module.network.nat_gateway_id }
output "nat_public_ipv4" { value = module.network.nat_public_ipv4 }
output "network_id" { value = module.network.vpc_id }
output "s3_endpoint_id" { value = aws_vpc_endpoint.s3.id }
