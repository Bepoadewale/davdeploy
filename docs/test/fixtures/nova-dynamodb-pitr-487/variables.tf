variable "run_id" {
  type        = string
  description = "Unique suffix for this disposable lifecycle test."

  validation {
    condition     = can(regex("^[a-z0-9-]{4,16}$", var.run_id))
    error_message = "run_id must contain 4 to 16 lowercase letters, digits, or hyphens."
  }
}
