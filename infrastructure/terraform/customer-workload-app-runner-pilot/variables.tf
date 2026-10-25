variable "region" {
  type        = string
  description = "AWS region for the customer workload pilot."
}

variable "expected_account_id" {
  type        = string
  description = "Account guard. Terraform fails if the caller is not in this AWS account."
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
  description = "DavDeploy customer connection identifier. It scopes deterministic workload names and tags."

  validation {
    condition     = can(regex("^[A-Za-z0-9-]{8,40}$", var.connection_id))
    error_message = "connection_id must be the non-secret DavDeploy connection identifier."
  }
}

variable "app_runner_ecr_access_role_arn" {
  type        = string
  description = "Customer-created App Runner ECR access role from the connection stack."
}

variable "app_runner_runtime_role_arn" {
  type        = string
  description = "Customer-created App Runner runtime role from the connection stack."
}

variable "customer_vpc_cidr" {
  type        = string
  description = "Dedicated same-account customer-sandbox VPC CIDR."
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
  description = "Create the App Runner service after the customer image has been pushed to ECR."
  default     = false
}

variable "image_identifier" {
  type        = string
  description = "Full ECR image URI with tag for the customer workload. Required when enable_service is true."
  default     = "placeholder.invalid/davdeploy-customer-workload:unset"
}

variable "service_name" {
  type        = string
  description = "Retained customer foundation/log-group name."
  default     = ""
}

variable "app_runner_service_name" {
  type        = string
  description = "App Runner service name, which must be at most 40 characters."
  default     = ""
}

variable "ecr_repository_name" {
  type        = string
  description = "ECR repository name for the customer workload image."
  default     = ""
}

variable "source_repository" {
  type        = string
  description = "Customer source repository URL used as pilot evidence."
  default     = "https://github.com/Bepoadewale/ai-platform-control-plane"
}

variable "source_commit" {
  type        = string
  description = "Customer source commit SHA used for the image build."
}

variable "plan_digest" {
  type        = string
  description = "davdeploy approved plan digest represented by this pilot execution."
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
