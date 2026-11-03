variable "region" { type = string }
variable "expected_account_id" { type = string }
variable "connection_id" { type = string }
variable "plan_digest" { type = string }
variable "service_name" { type = string }
variable "artifact_path" { type = string }
variable "handler" {
  type    = string
  default = "index.handler"
}

variable "runtime" {
  type    = string
  default = "python3.12"
}
