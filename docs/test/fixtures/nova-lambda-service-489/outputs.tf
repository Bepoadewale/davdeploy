output "function_name" {
  value = local.function_name
}

output "function_arn" {
  value = module.lambda_service.arn
}

output "role_name" {
  value = aws_iam_role.function.name
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.function.name
}
