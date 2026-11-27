terraform {
  required_version = ">= 1.10"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.45"
    }
  }
}

provider "aws" {
  region  = var.region
  profile = var.customer_profile != "" ? var.customer_profile : null
}
