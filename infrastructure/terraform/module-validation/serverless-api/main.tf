module "workload" {
  source              = "../../customer-workload-serverless-api"
  region              = var.region
  expected_account_id = var.expected_account_id
  connection_id       = var.test_id
  plan_digest         = var.plan_digest
  service_name        = "davdeploy-${var.test_id}-api"
  artifact_path       = "${path.module}/../delivery/lambda.zip"
}

output "api_endpoint" { value = module.workload.api_endpoint }
output "lambda_arn" { value = module.workload.lambda_arn }
