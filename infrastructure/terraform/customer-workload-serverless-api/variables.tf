variable "region" { type = string }
variable "expected_account_id" { type = string }
variable "connection_id" { type = string }
variable "project_id" { type = string }
variable "plan_digest" { type = string }
variable "service_name" { type = string }
variable "artifact_path" { type = string }
variable "customer_profile" {
  type        = string
  default     = ""
  description = "Optional named profile for customer workload resources. The Terraform backend continues to use the runner's platform credentials."
}
variable "handler" {
  type    = string
  default = "index.handler"
}

variable "runtime" {
  type    = string
  default = "python3.12"
}

variable "uploads_bucket_name" {
  type        = string
  default     = ""
  description = "Optional project-scoped private S3 bucket name supplied through a validated typed module reference."
}
