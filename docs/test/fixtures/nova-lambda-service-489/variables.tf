variable "account_id" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "run_id" {
  type = string
}

variable "handler_version" {
  type = string

  validation {
    condition     = contains(["v1", "v2"], var.handler_version)
    error_message = "handler_version must be v1 or v2."
  }
}
