variable "name" { type = string }
variable "tags" { type = map(string) }
variable "flag_name" {
  type    = string
  default = "davdeploy_demo"

  validation {
    condition     = can(regex("^[a-z][A-Za-z0-9_-]{0,63}$", var.flag_name))
    error_message = "flag_name must be a lowercase-starting AppConfig flag key."
  }
}
variable "flag_enabled" {
  type    = bool
  default = false
}

resource "aws_appconfig_application" "this" {
  name = var.name
  tags = var.tags
}

resource "aws_appconfig_environment" "this" {
  application_id = aws_appconfig_application.this.id
  name           = "production"
  tags           = var.tags
}

resource "aws_appconfig_configuration_profile" "this" {
  application_id = aws_appconfig_application.this.id
  location_uri   = "hosted"
  name           = "${var.name}-flags"
  type           = "AWS.AppConfig.FeatureFlags"
  tags           = var.tags
}

resource "aws_appconfig_hosted_configuration_version" "this" {
  application_id           = aws_appconfig_application.this.id
  configuration_profile_id = aws_appconfig_configuration_profile.this.configuration_profile_id
  content_type             = "application/json"
  content = jsonencode({
    flags = {
      (var.flag_name) = { name = var.flag_name }
    }
    values = {
      (var.flag_name) = { enabled = var.flag_enabled }
    }
    version = "1"
  })
}

resource "aws_appconfig_deployment_strategy" "this" {
  name                           = "${var.name}-linear"
  deployment_duration_in_minutes = 1
  final_bake_time_in_minutes     = 1
  growth_factor                  = 50
  growth_type                    = "LINEAR"
  replicate_to                   = "NONE"
  tags                           = var.tags
}

resource "aws_appconfig_deployment" "this" {
  application_id           = aws_appconfig_application.this.id
  configuration_profile_id = aws_appconfig_configuration_profile.this.configuration_profile_id
  configuration_version    = aws_appconfig_hosted_configuration_version.this.version_number
  deployment_strategy_id   = aws_appconfig_deployment_strategy.this.id
  description              = "Bounded DavDeploy feature flag rollout"
  environment_id           = aws_appconfig_environment.this.environment_id
  tags                     = var.tags
}

output "application_id" { value = aws_appconfig_application.this.id }
output "environment_id" { value = aws_appconfig_environment.this.environment_id }
output "configuration_profile_id" {
  value = aws_appconfig_configuration_profile.this.configuration_profile_id
}
output "configuration_version" {
  value = aws_appconfig_hosted_configuration_version.this.version_number
}
output "deployment_strategy_id" { value = aws_appconfig_deployment_strategy.this.id }
output "deployment_number" { value = aws_appconfig_deployment.this.deployment_number }
output "flag_name" { value = var.flag_name }
