variable "account_id" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "parameter_value" {
  type      = string
  sensitive = true
}

variable "test_id" {
  type = string

  validation {
    condition     = can(regex("^[0-9]{8}-[a-z0-9]{6}$", var.test_id))
    error_message = "test_id must be YYYYMMDD followed by six lowercase letters or digits."
  }
}
