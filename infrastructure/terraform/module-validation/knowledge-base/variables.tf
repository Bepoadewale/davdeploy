variable "region" {
  type    = string
  default = "us-east-1"
}

variable "test_id" { type = string }

variable "create_knowledge_base" {
  type    = bool
  default = false
}
