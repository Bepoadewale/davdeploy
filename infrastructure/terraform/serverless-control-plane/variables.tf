variable "region" {
  type        = string
  description = "AWS region for the davdeploy control plane."
  default     = "us-east-1"
}

variable "frontend_origin" {
  type        = string
  description = "Exact HTTPS Cloudflare Pages or custom-domain origin."

  validation {
    condition     = can(regex("^https://[^/]+$", var.frontend_origin))
    error_message = "frontend_origin must be one exact HTTPS origin without a trailing slash."
  }
}

variable "artifact_bucket" {
  type        = string
  description = "Existing private S3 bucket containing the verified Lambda package."
}

variable "artifact_key" {
  type        = string
  description = "Versioned S3 key for the verified Lambda zip package."
}

variable "artifact_object_version" {
  type        = string
  description = "Optional immutable S3 object version for the Lambda package."
  default     = null
}

variable "customer_execution_state_bucket" {
  type        = string
  description = "Versioned control-plane bucket used only for per-connection customer Terraform state."
}

variable "customer_execution_lock_table" {
  type        = string
  description = "Control-plane DynamoDB lock table used for per-connection customer Terraform state."
}

variable "customer_execution_artifact_key" {
  type        = string
  description = "Immutable S3 key for the reviewed customer execution runner archive."
}

variable "customer_execution_kms_key_arns" {
  type        = list(string)
  description = "Customer-managed KMS keys the isolated runner needs to decrypt its reviewed release and result artifacts."
  default     = []
}

variable "enable_customer_cloud_execution" {
  type        = bool
  description = "Explicitly enable bounded authenticated customer plan/apply submissions. Defaults to false."
  default     = false
}

variable "enable_github_app_read_only" {
  type        = bool
  description = "Explicitly enable the configured GitHub App for read-only private repository onboarding."
  default     = false
}

variable "github_app_id" {
  type        = string
  description = "Non-secret GitHub App ID used only when read-only App onboarding is enabled."
  default     = ""
}

variable "github_app_installation_id" {
  type        = string
  description = "Non-secret selected GitHub App installation ID used only when read-only App onboarding is enabled."
  default     = ""
}

variable "github_app_credential_secret_arn" {
  type        = string
  description = "Dedicated Secrets Manager ARN holding a JSON private-key.pem value; never place the key in Terraform variables or state."
  default     = ""

  validation {
    condition = !var.enable_github_app_read_only || alltrue([
      var.github_app_id != "",
      var.github_app_installation_id != "",
      var.github_app_credential_secret_arn != "",
    ])
    error_message = "Enabled GitHub App onboarding requires the App ID, installation ID, and a dedicated private-key secret ARN."
  }
}

variable "aws_connection_template_url" {
  type        = string
  description = "Immutable public S3 HTTPS URL for the reviewed customer AWS connection CloudFormation template. Supplied only by the protected Terraform-plan environment."
}

variable "cognito_domain_prefix" {
  type        = string
  description = "Globally unique Cognito managed-login domain prefix."
}

variable "google_identity_provider_enabled" {
  type        = bool
  description = "Expose Google after the provider is configured outside Terraform state."
  default     = false
}

variable "ses_identity_arn" {
  type        = string
  description = "Verified SES identity ARN for production OTP email. Empty uses Cognito default email delivery."
  default     = ""
}

variable "ses_from_address" {
  type        = string
  description = "Verified From address used when ses_identity_arn is set."
  default     = ""
}

variable "database_name" {
  type        = string
  description = "Aurora PostgreSQL database name."
  default     = "davdeploy"
}

variable "aurora_engine_version" {
  type        = string
  description = "Aurora PostgreSQL version approved for Data API and Serverless v2."
  default     = "16.15"
}

variable "aurora_min_capacity" {
  type        = number
  description = "Minimum Aurora capacity units."
  default     = 0
}

variable "aurora_seconds_until_auto_pause" {
  type        = number
  description = "Idle time before Aurora scales to zero when the selected engine supports auto-pause."
  default     = 900
}

variable "aurora_max_capacity" {
  type        = number
  description = "Maximum Aurora capacity units."
  default     = 2
}

variable "database_deletion_protection" {
  type        = bool
  description = "Protect the control-plane database from accidental deletion."
  default     = true
}

variable "monthly_budget_usd" {
  type        = number
  description = "Alerting threshold only. It does not automatically stop resources."
  default     = 50
}

variable "budget_notification_email" {
  type        = string
  description = "Optional operator email for budget alerts."
  default     = ""
  sensitive   = true
}

variable "nova_model_id" {
  type        = string
  description = "Amazon Nova 2 Lite inference profile."
  default     = "us.amazon.nova-2-lite-v1:0"
}
