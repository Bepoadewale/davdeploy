variable "region" {
  type        = string
  description = "AWS region for the hosted davdeploy runtime."
}

variable "enable_service" {
  type        = bool
  description = "Create the App Runner service only after the image has been pushed to ECR."
  default     = false
}

variable "oidc_jwks_url" {
  type        = string
  description = "Trusted production identity JWKS URL. Required before the hosted service can be enabled."
  default     = ""
}

variable "oidc_issuer" {
  type        = string
  description = "Exact trusted OIDC issuer. Required before the hosted service can be enabled."
  default     = ""
}

variable "oidc_audience" {
  type        = string
  description = "Exact davdeploy OIDC audience. Required before the hosted service can be enabled."
  default     = ""
}

variable "frontend_origin" {
  type        = string
  description = "Exact HTTPS origin of the separately hosted static frontend. Required before the hosted service can be enabled."
  default     = ""
}

variable "policy_url" {
  type        = string
  description = "HTTPS endpoint for the independent production OPA decision service. Required before the hosted service can be enabled."
  default     = ""
}

variable "enable_nova_model" {
  type        = bool
  description = "Enable governed Amazon Nova 2 Lite intent extraction and its least-privilege runtime permission."
  default     = false
}

variable "nova_model_id" {
  type        = string
  description = "Amazon Nova 2 Lite geographic inference profile ID."
  default     = "us.amazon.nova-2-lite-v1:0"

  validation {
    condition     = can(regex("^(us|eu|jp)\\.amazon\\.nova-2-lite-v1:0$", var.nova_model_id))
    error_message = "nova_model_id must be a geographic Amazon Nova 2 Lite inference profile."
  }
}

variable "nova_intent_schema_repair_attempts" {
  type        = number
  description = "Maximum locally validated Nova intent schema repairs, bounded from zero to two."
  default     = 1

  validation {
    condition = (
      var.nova_intent_schema_repair_attempts >= 0 &&
      var.nova_intent_schema_repair_attempts <= 2 &&
      floor(var.nova_intent_schema_repair_attempts) == var.nova_intent_schema_repair_attempts
    )
    error_message = "nova_intent_schema_repair_attempts must be an integer from zero to two."
  }
}

variable "image_identifier" {
  type        = string
  description = "Full ECR image URI with tag for the davdeploy runtime. Required when enable_service is true."
  default     = "placeholder.invalid/davdeploy:unset"
}

variable "customer_template_url" {
  type        = string
  description = "Public, versioned CloudFormation template URL used for customer read-only discovery onboarding."
}

variable "connection_secret_prefix" {
  type        = string
  description = "Secrets Manager prefix for per-connection ExternalIds."
  default     = "davdeploy/customer-connections"
}

variable "cpu" {
  type        = string
  description = "App Runner CPU size."
  default     = "256"
}

variable "memory" {
  type        = string
  description = "App Runner memory size."
  default     = "512"
}

variable "enable_durable_database" {
  type        = bool
  description = "Create private RDS PostgreSQL and wire App Runner to it. Required for production hosted mode."
  default     = false
}

variable "database_name" {
  type        = string
  description = "davdeploy control-plane PostgreSQL database name."
  default     = "davdeploy"
}

variable "database_instance_class" {
  type        = string
  description = "RDS instance class for the hosted davdeploy control plane."
  default     = "db.t4g.micro"
}

variable "database_allocated_storage" {
  type        = number
  description = "Allocated RDS storage in GiB."
  default     = 20
}

variable "database_backup_retention_days" {
  type        = number
  description = "RDS automated backup retention in days."
  default     = 7

  validation {
    condition     = var.database_backup_retention_days >= 7 && var.database_backup_retention_days <= 35
    error_message = "database_backup_retention_days must be between 7 and 35 days."
  }
}

variable "database_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for the production control-plane database."
  default     = true
}

variable "runtime_vpc_cidr" {
  type        = string
  description = "CIDR block for the optional hosted runtime VPC."
  default     = "10.42.0.0/16"

  validation {
    condition     = var.runtime_vpc_cidr == "10.42.0.0/16"
    error_message = "The controlled platform VPC CIDR must be 10.42.0.0/16."
  }
}

variable "monthly_platform_budget_usd" {
  type        = number
  description = "Monthly davdeploy platform cost guardrail. Alerts do not automatically stop resources."
  default     = 250

  validation {
    condition     = var.monthly_platform_budget_usd >= 25 && var.monthly_platform_budget_usd <= 5000
    error_message = "monthly_platform_budget_usd must be between 25 and 5000."
  }
}

variable "monitoring_notification_email" {
  type        = string
  description = "Operator email for platform budget and alarm notifications. Empty creates the controls without an email subscription."
  default     = ""
  sensitive   = true

  validation {
    condition     = var.monitoring_notification_email == "" || can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.monitoring_notification_email))
    error_message = "monitoring_notification_email must be empty or a valid email address."
  }
}
