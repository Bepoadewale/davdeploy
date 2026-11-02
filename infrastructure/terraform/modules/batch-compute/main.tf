variable "name" { type = string }
variable "service_role_arn" { type = string }
variable "instance_role_arn" { type = string }
variable "subnet_ids" { type = list(string) }
variable "security_group_ids" { type = list(string) }
variable "image" { type = string }
variable "tags" { type = map(string) }

resource "aws_batch_compute_environment" "this" {
  compute_environment_name = var.name
  type                     = "MANAGED"
  state                    = "ENABLED"
  service_role             = var.service_role_arn
  compute_resources {
    type               = "FARGATE"
    max_vcpus          = 16
    subnets            = var.subnet_ids
    security_group_ids = var.security_group_ids
  }
  tags = var.tags
}

resource "aws_batch_job_queue" "this" {
  name                 = var.name
  state                = "ENABLED"
  priority             = 1
  compute_environments = [aws_batch_compute_environment.this.arn]
  tags                 = var.tags
}

resource "aws_batch_job_definition" "this" {
  name                  = var.name
  type                  = "container"
  platform_capabilities = ["FARGATE"]
  container_properties = jsonencode({
    image            = var.image
    executionRoleArn = var.instance_role_arn
    resourceRequirements = [
      { type = "VCPU", value = "0.25" },
      { type = "MEMORY", value = "512" }
    ]
  })
  tags = var.tags
}

output "job_queue_arn" { value = aws_batch_job_queue.this.arn }
