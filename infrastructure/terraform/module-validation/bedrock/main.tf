locals {
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

module "runtime" {
  source = "../../modules/bedrock-runtime"
  name   = "davdeploy-${var.test_id}"
  allowed_model_arns = [
    "arn:aws:bedrock:${var.region}::foundation-model/amazon.nova-micro-v1:0",
  ]
  tags = local.tags
}

output "guardrail_id" { value = module.runtime.guardrail_id }
