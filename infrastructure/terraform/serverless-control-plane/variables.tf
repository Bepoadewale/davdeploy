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

variable "application_rate_limit_per_minute" {
  type        = number
  description = "Per-Lambda-instance fallback limit for non-health API requests. API Gateway route limits remain the primary distributed control."
  default     = 60

  validation {
    condition     = var.application_rate_limit_per_minute >= 1 && var.application_rate_limit_per_minute <= 600
    error_message = "application_rate_limit_per_minute must be between 1 and 600."
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

variable "enable_nova_plan_reviews" {
  type        = bool
  description = "Enable encrypted, tenant-scoped Nova saved-plan review storage. This does not enable apply or destroy."
  default     = false
}

variable "enable_nova_plan_role_verification" {
  type        = bool
  description = "Allow the API to verify trust/account identity for customer roles named davdeployPlan-*. This does not attest the role's effective permissions or enable customer deployment. Defaults to false."
  default     = false
}

variable "nova_plan_artifact_bucket" {
  type        = string
  description = "Existing versioned SSE-KMS Terraform plan bucket used for Nova artifacts when review storage is enabled."
  default     = ""

  validation {
    condition     = var.nova_plan_artifact_bucket == "" || can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.nova_plan_artifact_bucket))
    error_message = "nova_plan_artifact_bucket must be an S3 bucket name."
  }
}

variable "nova_plan_kms_key_arn" {
  type        = string
  description = "Exact KMS key ARN used by the existing Terraform plan bucket for Nova saved-plan artifacts."
  default     = ""

  validation {
    condition     = var.nova_plan_kms_key_arn == "" || can(regex("^arn:aws:kms:[a-z0-9-]+:[0-9]{12}:key/[A-Za-z0-9-]+$", var.nova_plan_kms_key_arn))
    error_message = "nova_plan_kms_key_arn must be a concrete AWS KMS key ARN."
  }
}

variable "nova_plan_runner_release_kms_key_arn" {
  type        = string
  description = "Exact KMS key used to encrypt the immutable Lambda release archive that contains the fixed Nova runner."
  default     = ""

  validation {
    condition     = var.nova_plan_runner_release_kms_key_arn == "" || can(regex("^arn:aws:kms:[a-z0-9-]+:[0-9]{12}:key/[A-Za-z0-9-]+$", var.nova_plan_runner_release_kms_key_arn))
    error_message = "nova_plan_runner_release_kms_key_arn must be a concrete AWS KMS key ARN."
  }
}

variable "enable_nova_plan_only_runner" {
  type        = bool
  description = "Provision the isolated fixed Nova plan-only CodeBuild runner and expose it to the API. Keep disabled until its required state and policy gates are ready."
  default     = false

  validation {
    condition     = !var.enable_nova_plan_only_runner || (var.nova_plan_artifact_bucket != "" && var.nova_plan_kms_key_arn != "" && var.nova_plan_runner_release_kms_key_arn != "" && var.artifact_key != "" && var.artifact_object_version != null && var.artifact_object_version != "")
    error_message = "The Nova plan-only runner requires versioned plan storage, a fixed release KMS key, and an exact immutable Lambda package version."
  }

  validation {
    condition     = !var.enable_nova_plan_only_runner || var.enable_nova_plan_reviews
    error_message = "The Nova plan-only runner requires Nova plan reviews so the API has the permissions needed to stage and reconcile requests."
  }

  validation {
    condition     = !var.enable_nova_plan_only_runner || var.enable_nova_plan_role_verification
    error_message = "The Nova plan-only runner requires plan-role trust/account verification to be enabled."
  }
}

variable "enable_nova_terraform_state_storage" {
  type        = bool
  description = "Provision the private versioned KMS state bucket. This does not enable the HTTP API or change the backend-free Nova runner."
  default     = false
}

variable "enable_nova_terraform_state_api" {
  type        = bool
  description = "Enable the tenant-scoped HTTP state API and remote-state worker path. Defaults off."
  default     = false

  validation {
    condition = !var.enable_nova_terraform_state_api || (
      var.enable_nova_plan_only_runner &&
      var.enable_nova_terraform_state_storage &&
      can(regex("^https://[A-Za-z0-9.-]+(:[0-9]+)?$", var.nova_terraform_state_api_url))
    )
    error_message = "Nova remote state requires the isolated plan runner, encrypted state storage, and an HTTPS state API origin."
  }
}

variable "nova_terraform_state_api_url" {
  type        = string
  description = "HTTPS origin of the public DavDeploy state API; required only when remote state is enabled."
  default     = ""
}

variable "enable_customer_cloud_execution" {
  type        = bool
  description = "Explicitly enable bounded authenticated customer plan/apply submissions. Defaults to false."
  default     = false
}

variable "enable_serverless_api_hosted_certification" {
  type        = bool
  description = "Enable the isolated Lambda/API certification route for allowlisted workspaces only. Defaults to false."
  default     = false
}

variable "serverless_certification_workspace_ids" {
  type        = list(string)
  description = "Workspace IDs permitted to use the isolated Lambda/API certification route. Empty denies all workspaces."
  default     = []

  validation {
    condition = alltrue([
      for workspace_id in var.serverless_certification_workspace_ids : can(regex("^[A-Za-z0-9_-]{1,128}$", workspace_id))
    ])
    error_message = "Certification workspace IDs must contain only letters, numbers, underscores, or hyphens."
  }
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

variable "resend_invitation_parameter_name" {
  type        = string
  description = "Optional Standard SSM SecureString name containing the Resend invitation API key. The secret value is never a Terraform input."
  default     = ""
}

variable "edge_origin_token_parameter_name" {
  type        = string
  description = "Optional SecureString SSM parameter holding the Cloudflare Worker origin token. Empty keeps the direct API path available during a staged edge rollout."
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
