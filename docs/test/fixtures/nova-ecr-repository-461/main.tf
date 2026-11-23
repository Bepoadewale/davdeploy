terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region              = "us-east-1"
  allowed_account_ids = ["654654474502"]
}

module "repository" {
  source = "../../../../infrastructure/terraform/modules/ecr"

  name = "davdeploy-nova-ecr-461-a1"
  tags = {
    DavDeployTestRun = "nova-ecr-repository-461"
    Environment      = "test"
    ManagedBy        = "Terraform"
    Purpose          = "DavDeploy disposable ECR repository lifecycle test"
  }
}

output "repository_url" {
  value = module.repository.repository_url
}
