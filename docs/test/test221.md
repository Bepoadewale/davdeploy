# test221

Date: 2026-11-19
Execution type: Terraform formatting and schema validation only; no AWS workload.
Customer repository: `Bepoadewale/davdeploy`, local fixture `tests/fixtures/customer-ecs-express-health`
Commit: uncommitted working tree based on `ec937ed257eec5eb0a21f69519df337a90bd79c0`
AWS account: `654654474502` (identity read only)
AWS region: `us-east-1`

## Resources created

None. The new root is opt-in and has not been applied to AWS.

## Commands executed

- `terraform fmt -recursive infrastructure/terraform/customer-workload-ecs-express-pilot`
- `terraform -chdir=infrastructure/terraform/customer-workload-ecs-express-pilot init -backend=false -input=false`
- `terraform -chdir=infrastructure/terraform/customer-workload-ecs-express-pilot validate`
- `AWS_PROFILE=ai-platform-pilot-key aws sts get-caller-identity`
- Read-only VPC and subnet inventory for the default VPC.

## Observed result

Terraform validation passed with AWS provider `6.73.0`. AWS documentation states
App Runner closed to new customers on April 30, 2026 and recommends ECS Express
Mode for new container workloads. The prior App Runner service request returned
an account-level restriction; the ECS Express customer service and its
lifecycle have not yet been tested.

## Teardown

Not applicable. This test created no AWS resources.

## Final boundary

This is static design and provider-schema evidence only. No Nova customer
workload or ECS Express service is claimed as applied or certified. The hosted
control plane and its state, runtime, queues, and API were not touched.
