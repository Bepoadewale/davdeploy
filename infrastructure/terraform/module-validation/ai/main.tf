locals {
  tags = { ManagedBy = "terraform", Purpose = "davdeploy-module-validation", TestId = var.test_id }
}

module "stream" {
  source = "../../modules/kinesis-stream"
  name   = "davdeploy-${var.test_id}"
  tags   = local.tags
}

output "stream_arn" { value = module.stream.arn }
