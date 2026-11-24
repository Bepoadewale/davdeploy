variable "account_id" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "run_id" {
  type = string

  validation {
    condition     = can(regex("^[a-z0-9-]{6,24}$", var.run_id))
    error_message = "run_id must contain 6-24 lowercase letters, digits, or hyphens."
  }
}

variable "bucket_name" {
  type = string

  validation {
    condition     = startswith(var.bucket_name, "davdeploy-nova-artifacts-491-")
    error_message = "bucket_name must use the dedicated PR #491 test prefix."
  }
}
