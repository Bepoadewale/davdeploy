variable "region" {
  type        = string
  description = "AWS Region for the customer workload pilot."
}

variable "customer_profile" {
  type        = string
  description = "Optional temporary customer AWS CLI profile used by the execution runner."
  default     = ""

  validation {
    condition     = var.customer_profile == "" || can(regex("^[A-Za-z0-9_-]{1,64}$", var.customer_profile))
    error_message = "customer_profile must be empty or a simple temporary AWS profile name."
  }
}

variable "expected_account_id" {
  type        = string
  description = "Account guard. Terraform fails if the caller is outside this account."
}

variable "deployment_scope" {
  type        = string
  description = "Required placement label for the same-account customer sandbox."
  default     = "customer-sandbox"

  validation {
    condition     = var.deployment_scope == "customer-sandbox"
    error_message = "deployment_scope must be customer-sandbox."
  }
}

variable "connection_id" {
  type        = string
  description = "Non-secret test run identifier used in resource names and tags."

  validation {
    condition     = can(regex("^[a-z0-9-]{8,30}$", var.connection_id))
    error_message = "connection_id must contain 8 to 30 lowercase letters, digits, or hyphens."
  }
}

variable "project_id" {
  type        = string
  description = "Tenant project identifier used to scope ECS Express resources and remote state."

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,64}$", var.project_id))
    error_message = "project_id must contain 1 to 64 letters, digits, underscores, or hyphens."
  }
}

variable "customer_vpc_cidr" {
  type        = string
  description = "Dedicated public-subnet VPC CIDR for the same-account customer sandbox."
  default     = "10.84.0.0/16"

  validation {
    condition     = var.customer_vpc_cidr == "10.84.0.0/16"
    error_message = "The controlled pilot customer VPC CIDR must be 10.84.0.0/16."
  }
}

variable "platform_vpc_cidr" {
  type        = string
  description = "Platform VPC CIDR used only by the collision guard."
  default     = "10.42.0.0/16"

  validation {
    condition     = var.platform_vpc_cidr == "10.42.0.0/16"
    error_message = "The controlled pilot platform VPC CIDR must be 10.42.0.0/16."
  }
}

variable "enable_service" {
  type        = bool
  description = "Create the ECS Express Mode service after an immutable image is pushed to ECR."
  default     = false
}

variable "image_identifier" {
  type        = string
  description = "Immutable ECR image URI and tag for the customer workload."
  default     = "placeholder.invalid/davdeploy-customer-workload:unset"

  validation {
    condition = !var.enable_service || can(regex(
      "^${var.expected_account_id}\\.dkr\\.ecr\\.${var.region}\\.amazonaws\\.com/davdeploy-ecs-${substr(sha256("${var.connection_id}:${var.project_id}:${var.region}"), 0, 24)}@sha256:[a-f0-9]{64}$",
      var.image_identifier,
    ))
    error_message = "Enabled ECS Express services require a digest-pinned image in this project's same-account ECR repository."
  }
}

variable "source_repository" {
  type        = string
  description = "Repository or local source identifier recorded on customer resources."
}

variable "source_commit" {
  type        = string
  description = "Full immutable source commit recorded on customer resources."

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.source_commit))
    error_message = "source_commit must be a full 40-character lowercase Git SHA-1."
  }
}

variable "plan_digest" {
  type        = string
  description = "Identifier for the approved customer test plan represented by these resources."

  validation {
    condition     = can(regex("^[a-f0-9]{64}$", var.plan_digest))
    error_message = "plan_digest must be a lowercase SHA-256 digest."
  }
}
