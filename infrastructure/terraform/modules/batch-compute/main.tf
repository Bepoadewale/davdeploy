variable "name" { type = string }
variable "service_role_arn" {
  type        = string
  default     = null
  description = "Optional Batch service role ARN; omit for Fargate managed compute environments."
}
variable "instance_role_arn" { type = string }
variable "subnet_ids" { type = list(string) }
variable "security_group_ids" { type = list(string) }
variable "image" { type = string }
variable "log_group_name" { type = string }
variable "region" { type = string }
variable "tags" { type = map(string) }
variable "assign_public_ip" {
  type        = bool
  default     = true
  description = "Whether Fargate tasks receive a public IPv4 address."
}
variable "retry_attempts" {
  type        = number
  default     = null
  description = "Optional bounded retry count for the Batch job definition."
  validation {
    condition     = var.retry_attempts == null || (var.retry_attempts >= 1 && var.retry_attempts <= 10)
    error_message = "retry_attempts must be omitted or between 1 and 10."
  }
}
variable "timeout_seconds" {
  type        = number
  default     = null
  description = "Optional per-attempt job timeout in seconds."
  validation {
    condition     = var.timeout_seconds == null || (var.timeout_seconds >= 60 && var.timeout_seconds <= 86400)
    error_message = "timeout_seconds must be omitted or between 60 and 86400."
  }
}
variable "max_vcpus" {
  type        = number
  default     = 16
  description = "Maximum vCPU capacity for the managed Fargate compute environment."
  validation {
    condition     = var.max_vcpus >= 1 && var.max_vcpus <= 16
    error_message = "max_vcpus must be between 1 and the module's 16-vCPU bound."
  }
}

resource "aws_batch_compute_environment" "this" {
  compute_environment_name = var.name
  type                     = "MANAGED"
  state                    = "ENABLED"
  service_role             = var.service_role_arn
  compute_resources {
    type               = "FARGATE"
    max_vcpus          = var.max_vcpus
    subnets            = var.subnet_ids
    security_group_ids = var.security_group_ids
  }
  tags = var.tags
}

resource "aws_batch_job_queue" "this" {
  name     = var.name
  state    = "ENABLED"
  priority = 1
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.this.arn
  }
  tags = var.tags
}

resource "aws_batch_job_definition" "this" {
  name                  = var.name
  type                  = "container"
  platform_capabilities = ["FARGATE"]
  container_properties = jsonencode({
    image            = var.image
    executionRoleArn = var.instance_role_arn
    # Public-IP assignment is configurable for callers that use private
    # subnets with approved endpoints or NAT-based egress.
    networkConfiguration = {
      assignPublicIp = var.assign_public_ip ? "ENABLED" : "DISABLED"
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = var.log_group_name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "davdeploy"
      }
    }
    resourceRequirements = [
      { type = "VCPU", value = "0.25" },
      { type = "MEMORY", value = "512" }
    ]
  })
  dynamic "retry_strategy" {
    for_each = var.retry_attempts == null ? [] : [var.retry_attempts]
    content {
      attempts = retry_strategy.value
    }
  }
  dynamic "timeout" {
    for_each = var.timeout_seconds == null ? [] : [var.timeout_seconds]
    content {
      attempt_duration_seconds = timeout.value
    }
  }
  tags = var.tags
}

output "job_queue_arn" { value = aws_batch_job_queue.this.arn }
output "job_definition_arn" { value = aws_batch_job_definition.this.arn }
