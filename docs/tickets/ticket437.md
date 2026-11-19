# ticket437

PR: https://github.com/Bepoadewale/davdeploy/pull/437
Branch: `feat/customer-ecs-express-pilot-221`

## Problem / goal

AWS closed App Runner to new customers on April 30, 2026. The platform AWS
account is therefore unable to create the App Runner service required by the
current customer pilot. Add an owner-controlled ECS Express Mode pilot that
works for new AWS customers and preserves the account boundary and hosted
control-plane separation.

## Current repo state

Commit `5a5a464` adds a Terraform root for a dedicated customer VPC, ECR image
repository, ECS task execution and infrastructure roles, and an opt-in ECS
Express Mode service. It uses local Terraform state, a one-task ceiling, public
subnets, no NAT gateway, and no ECS task role. Account-side service and
lifecycle validation is still outstanding.

## Research / references used

- [AWS App Runner availability change](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)
- [Amazon ECS Express Mode overview](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html)
- [ECS Express Mode creation and IAM roles](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html)
- [Terraform `aws_ecs_express_gateway_service`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_express_gateway_service)

## Work planned for the PR

Validate the full Terraform root set in CI. Prepare a fresh same-account ECS
Express customer run using local state, build and push the health fixture by
immutable digest, verify live health and update/recovery behavior, then review
a saved destroy plan and verify absence after explicit cleanup authorization.

## Acceptance criteria

- The new root validates with the pinned AWS provider and is included in the
  Terraform validation script.
- Account and Region guards fail closed; customer resources retain the
  same-account boundary, unique run ID, and separate roles.
- ECS Express Mode starts the exact image digest, reaches steady state, and
  returns the expected `/healthz` response.
- A saved plan can update the workload and demonstrate recovery from a failed
  revision.
- A reviewed saved destroy plan removes only the test resources. Independent
  AWS inventory and local Terraform state prove absence.
- The hosted control plane and its state, runtime, queues, and API remain
  untouched. No hosted Nova apply or cross-account isolation is claimed.

## Acceptance status

In progress. The new root passes local Terraform validation and the health
fixture returns the expected response when run locally. Live ECS Express
service, update/recovery, destroy, and absence evidence are pending.

## Tests / validation performed

- `terraform fmt -recursive infrastructure/terraform/customer-workload-ecs-express-pilot`
- `terraform -chdir=infrastructure/terraform/customer-workload-ecs-express-pilot init -backend=false -input=false`
- `terraform -chdir=infrastructure/terraform/customer-workload-ecs-express-pilot validate` with AWS provider `6.73.0`
- `terraform fmt -check -recursive infrastructure/terraform`
- `python3 scripts/check_doc_conventions.py`
- `git diff --check`
- Host-local `/healthz` request returned `{"status":"ok","scope":"same-account-customer-sandbox"}`.

## Evidence files produced

- `docs/test/test437.md`
- `docs/architecture/same-account-pilot.md`
- `infrastructure/terraform/customer-workload-ecs-express-pilot/README.md`

## Boundaries

Do not modify the existing hosted control plane, its Terraform state or locks,
runtime, queues, or service configuration. The ECS pilot uses a fresh
same-account customer VPC and local Terraform state. Do not enable Nova apply,
claim a Nova customer workload was applied, or describe the same-account VPC
as cross-account isolation. Do not delete customer resources or local files
without explicit approval.

## Follow-up work

Run the customer lifecycle test with a reviewed plan. Obtain explicit cleanup
authorization for the exact ECS Express resources before teardown. Keep PR #399
draft until its separate hosted Nova acceptance gates are met.
