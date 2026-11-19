# ticket221

PR: [AWS App Runner new-customer restriction and ECS Express migration issue](https://github.com/Bepoadewale/davdeploy/issues/221)
Branch: `feat/customer-ecs-express-pilot-221`

## Problem / goal

The owner-controlled customer pilot uses App Runner, but AWS closed App Runner
to new customers on April 30, 2026. The tested platform account returns an
account-level rejection when asked to create a new App Runner service. Provide
an equivalent customer workload pilot using ECS Express Mode while keeping the
hosted DavDeploy control plane untouched.

## Current repo state

A new `customer-workload-ecs-express-pilot` Terraform root exists with a local
state design, dedicated same-account customer VPC, ECR repository, ECS task
execution and infrastructure roles, and an opt-in ECS Express service. The
service is bounded to one task and uses no NAT gateway. AWS resources have not
been created through this root.

## Research / references used

- [AWS App Runner availability change](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)
- [Amazon ECS Express Mode overview](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html)
- [Terraform `aws_ecs_express_gateway_service`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_express_gateway_service)

## Work planned for the PR

Validate the new Terraform root and repository docs, run a fresh same-account
ECS Express customer test with isolated local Terraform state, and record live
health and teardown evidence if the account accepts the service.

## Acceptance criteria

- Account and Region guards fail closed and the customer resource tags retain
the same-account boundary.
- Terraform uses the AWS provider version that implements
  `aws_ecs_express_gateway_service` and validates without warnings.
- A fresh ECS Express customer service starts from an immutable ECR digest,
  reaches steady state, and returns the expected `/healthz` response.
- An exact saved destroy plan removes only test resources; independent AWS
  reads and local state prove absence.
- No hosted control-plane runtime, state, queues, or API are changed.

## Acceptance status

In progress. Static validation passed; the AWS service and lifecycle acceptance
run is not complete.

## Tests / validation performed

`terraform fmt` and `terraform validate` passed for the new root with AWS
provider `6.73.0`. Repository-wide checks and live ECS Express validation are
pending.

## Evidence files produced

- `docs/test/test221.md`
- `infrastructure/terraform/customer-workload-ecs-express-pilot/README.md`

## Boundaries

Keep the existing hosted control plane, its state bucket, lock table, runtime,
queues, and deployment settings untouched. Use only a fresh same-account
customer target and local Terraform state. Do not claim hosted Nova apply or
cross-account isolation. Do not delete non-container files or resources without
explicit approval.

## Follow-up work

Confirm the deployment test's teardown scope and record ECS service health,
updates, recovery, and independent absence checks. Keep PR #399 draft until its
separate hosted Nova acceptance gates are met.
