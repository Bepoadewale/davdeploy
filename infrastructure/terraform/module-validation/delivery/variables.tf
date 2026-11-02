variable "region" {
  type    = string
  default = "us-east-1"
}

variable "test_id" {
  type        = string
  description = "A lowercase, unique suffix for an isolated disposable test."
}
