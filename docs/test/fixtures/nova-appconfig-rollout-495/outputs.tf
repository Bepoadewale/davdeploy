output "account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "application_id" {
  value = module.feature_flags.application_id
}

output "environment_id" {
  value = module.feature_flags.environment_id
}

output "configuration_profile_id" {
  value = module.feature_flags.configuration_profile_id
}

output "configuration_version" {
  value = module.feature_flags.configuration_version
}

output "deployment_strategy_id" {
  value = module.feature_flags.deployment_strategy_id
}

output "deployment_number" {
  value = module.feature_flags.deployment_number
}

output "flag_name" {
  value = module.feature_flags.flag_name
}
