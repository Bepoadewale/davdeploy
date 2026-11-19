output "ecr_repository_url" {
  value       = aws_ecr_repository.workload.repository_url
  description = "Private ECR repository for the immutable customer test image."
}

output "ecs_express_service_arn" {
  value       = var.enable_service ? aws_ecs_express_gateway_service.workload[0].service_arn : null
  description = "ECS Express Mode service ARN when enabled."
}

output "ingress_paths" {
  value       = var.enable_service ? aws_ecs_express_gateway_service.workload[0].ingress_paths : []
  description = "ECS-managed customer workload ingress paths when enabled."
}

output "customer_vpc_id" {
  value       = aws_vpc.customer.id
  description = "Dedicated same-account customer-sandbox VPC."
}

output "customer_public_subnet_ids" {
  value       = aws_subnet.public[*].id
  description = "Public subnets used by the bounded ECS Express customer test."
}

output "execution_role_arn" {
  value       = aws_iam_role.execution.arn
  description = "Customer ECS task execution role for image pulls and logs."
}

output "infrastructure_role_arn" {
  value       = aws_iam_role.infrastructure.arn
  description = "Customer role assumed by ECS to manage Express service infrastructure."
}

output "pilot_scope" {
  value = {
    execution_boundary = "REAL_AWS_CREATE_VALIDATE_DESTROY"
    account_boundary   = "SAME_ACCOUNT_PILOT_NOT_CROSS_ACCOUNT"
    deployment_scope   = var.deployment_scope
    customer_vpc_cidr  = var.customer_vpc_cidr
    platform_vpc_cidr  = var.platform_vpc_cidr
    source_repository  = var.source_repository
    source_commit      = var.source_commit
    plan_digest        = var.plan_digest
    service            = "ecs-express-mode"
    nat_gateway        = false
    max_task_count     = 1
  }
}
