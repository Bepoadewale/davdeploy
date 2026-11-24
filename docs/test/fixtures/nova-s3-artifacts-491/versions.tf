terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.100.0"
    }
  }
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.account_id]
}

data "aws_caller_identity" "current" {}

check "expected_account" {
  assert {
    condition     = data.aws_caller_identity.current.account_id == var.account_id
    error_message = "AWS caller account does not match the expected test account."
  }
}
