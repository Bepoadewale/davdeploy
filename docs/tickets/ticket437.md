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

Commit `33c8e08` adds a Terraform root for a dedicated customer VPC, ECR image
repository, ECS task execution and infrastructure roles, and an opt-in ECS
Express Mode service. It uses local Terraform state, a one-task ceiling, public
subnets, no NAT gateway, and no ECS task role. A direct same-account customer
run now proves creation, live health, and teardown without using the hosted
control plane.

## Research / references used

- [AWS App Runner availability change](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)
- [Amazon ECS Express Mode overview](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html)
- [ECS Express Mode creation and IAM roles](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html)
- [Updating an ECS Express Mode service](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-update-full.html)
- [ECS Express Mode best practices and rollback](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-best-practices.html)
- [Terraform `aws_ecs_express_gateway_service`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_express_gateway_service)

## Work planned for the PR

Validate the full Terraform root set in CI. Add a health fixture that reports
its release version and can deliberately fail readiness. Run a fresh
same-account ECS Express lifecycle using local state and immutable image
digests: create and verify v1, update to healthy v2, deploy a failed-health
revision and observe service rollback, verify recovery on v2, then apply a
reviewed saved destroy plan and independently verify absence. Do not use or
modify the hosted control plane. **Completed in a second direct customer-side
run on 2026-11-19; see `docs/test/test437.md`.**

## Acceptance criteria

- The new root validates with the pinned AWS provider and is included in the
  Terraform validation script.
- Account and Region guards fail closed; customer resources retain the
  same-account boundary, unique run ID, and separate roles.
- ECS Express Mode started the exact image digest, reached steady state, and
  returned the expected `/healthz` response. **Passed.**
- A saved plan updates the workload to v2; a controlled failed-health revision
  rolls back to the prior healthy service, and the service recovers to v2.
  **Passed.** v2 updated in place and returned healthy `/version` and
  `/healthz`; the failed-health revision triggered the ECS circuit breaker,
  and the live endpoint returned healthy v2 after rollback.
- A reviewed saved destroy plan removed all 15 Terraform-managed test
  resources. Independent AWS reads and empty local Terraform state confirm no
  running workload, VPC, load balancer, image repository, role, or log group.
  AWS retains an `INACTIVE` service-history record with zero desired, running,
  and pending tasks.
- The hosted control plane and its state, runtime, queues, and API remain
  untouched. No hosted Nova apply or cross-account isolation is claimed.

## Acceptance status

Customer-side creation, live health, and Terraform teardown passed in account
`654654474502`; independent reads confirm no billable workload remains. The
ECS service is retained by AWS as `INACTIVE` history with zero tasks, and an
empty default cluster record remains. A second isolated lifecycle run passed
the healthy v1-to-v2 update, failed-health circuit-breaker rollback, v2 health
recovery, and saved-plan teardown. This is direct Terraform evidence, not a
Nova-initiated apply; the hosted control plane was untouched. On 2026-11-19,
the goal owner accepted the isolated customer-side plan, apply, health,
update/recovery, and teardown evidence for the general Nova infrastructure goal
in place of a hosted customer apply under the required control-plane isolation.
It does not establish Nova generation, authorization, dispatch, or
cross-account isolation.

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
runtime, queues, or service configuration. The ECS pilot used a fresh
same-account customer VPC and local Terraform state, then removed its billable
workload resources after health verification. Describe this as direct
customer-side Terraform evidence; do not claim Nova initiated the apply or call
the same-account VPC cross-account isolation.

## Follow-up work

The update/recovery lifecycle test has passed for this same-account pilot.
Broader Nova-specific authorization, dispatch, cross-account isolation, and
per-root scenario acceptance remain outside this evidence. No hosted Nova
apply is claimed by this PR.
