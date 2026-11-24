variable "region" {
  type    = string
  default = "us-east-1"
}

variable "test_id" { type = string }

variable "redis_auth_token" {
  type      = string
  sensitive = true
}
