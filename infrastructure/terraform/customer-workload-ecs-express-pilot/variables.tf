variable "region" {
  type        = string
  description = "AWS Region for the customer workload pilot."
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
}
