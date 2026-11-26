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
  validation {
    condition     = var.region == "us-east-1"
    error_message = "This disposable validation root is restricted to us-east-1."
  }
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
  region              = var.region
  allowed_account_ids = ["654654474502"]
  default_tags {
    tags = local.tags
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  name                     = "davdeploy-${var.test_id}"
  task_execution_role_name = "${local.name}-execution"
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-private-batch-endpoints-517"
    TestId    = var.test_id
    ExpiresAt = var.expires_at
  }
  interface_services = toset(["ecr.api", "ecr.dkr", "logs"])
}

resource "aws_vpc" "test" {
  cidr_block           = "10.241.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(local.tags, { Name = local.name })
}

resource "aws_subnet" "private" {
  for_each                = { for index, az in var.availability_zones : index => az }
  vpc_id                  = aws_vpc.test.id
  cidr_block              = cidrsubnet(aws_vpc.test.cidr_block, 4, each.key)
  availability_zone       = each.value
  map_public_ip_on_launch = false
  tags                    = merge(local.tags, { Name = "${local.name}-private-${each.key}" })
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.test.id
  tags   = merge(local.tags, { Name = "${local.name}-private" })
}

resource "aws_route_table_association" "private" {
  for_each       = aws_subnet.private
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

module "ecr" {
  source = "../../modules/ecr"
  name   = local.name
  tags   = local.tags
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

resource "aws_iam_service_linked_role" "batch" {
  aws_service_name = "batch.amazonaws.com"
  description      = "AWS Batch service-linked role owned by the PR 517 disposable test."
}

resource "aws_iam_role" "task_execution" {
  name               = local.task_execution_role_name
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
  vpc_id      = aws_vpc.test.id
  egress      = []
  tags        = local.tags
}

resource "aws_security_group" "endpoints" {
  name        = "${local.name}-endpoints"
  description = "HTTPS ingress from the test Batch security group."
  vpc_id      = aws_vpc.test.id
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
  vpc_id              = aws_vpc.test.id
  service_name        = "com.amazonaws.${var.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  ip_address_type     = "ipv4"
  subnet_ids          = values(aws_subnet.private)[*].id
  security_group_ids  = [aws_security_group.endpoints.id]
  tags                = merge(local.tags, { Name = "${local.name}-${replace(each.key, ".", "-")}" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.test.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  ip_address_type   = "ipv4"
  route_table_ids   = [aws_route_table.private.id]
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
  instance_role_arn  = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${local.task_execution_role_name}"
  subnet_ids         = values(aws_subnet.private)[*].id
  security_group_ids = [aws_security_group.batch.id]
  image              = "${module.ecr.repository_url}@${var.image_digest}"
  log_group_name     = aws_cloudwatch_log_group.batch.name
  region             = var.region
  tags               = local.tags
  assign_public_ip   = false
  retry_attempts     = 1
  timeout_seconds    = 300
  max_vcpus          = 1
  depends_on         = [aws_iam_service_linked_role.batch, aws_iam_role_policy_attachment.task_execution]
}

output "account_id" { value = data.aws_caller_identity.current.account_id }
output "batch_job_definition_arn" { value = module.batch.job_definition_arn }
output "batch_job_definition_name" { value = local.name }
output "batch_job_queue_name" { value = local.name }
output "image_repository_url" { value = module.ecr.repository_url }
output "interface_endpoint_ids" { value = { for service, endpoint in aws_vpc_endpoint.interface : service => endpoint.id } }
output "log_group_name" { value = aws_cloudwatch_log_group.batch.name }
output "network_id" { value = aws_vpc.test.id }
output "s3_endpoint_id" { value = aws_vpc_endpoint.s3.id }
