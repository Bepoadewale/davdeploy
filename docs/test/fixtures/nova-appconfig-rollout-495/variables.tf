variable "region" {
  type    = string
  default = "us-east-1"
}

variable "test_id" {
  type = string

  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9-]{5,31}$", var.test_id))
    error_message = "test_id must be a unique 6-32 character alphanumeric/hyphen value."
  }
}

variable "flag_revisions" {
  type    = map(bool)
  default = { baseline = false }
}

variable "active_revision" {
  type    = string
  default = "baseline"
}
