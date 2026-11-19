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
- [Terraform `aws_ecs_express_gateway_service`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_express_gateway_service)

## Work planned for the PR

Validate the full Terraform root set in CI. Prepare a fresh same-account ECS
Express customer run using local state, build and push the health fixture by
immutable digest, verify live health, then apply a reviewed saved destroy plan
and independently verify that billable workload resources are absent. Update
and recovery behavior remains a follow-up.

## Acceptance criteria

- The new root validates with the pinned AWS provider and is included in the
  Terraform validation script.
- Account and Region guards fail closed; customer resources retain the
  same-account boundary, unique run ID, and separate roles.
- ECS Express Mode started the exact image digest, reached steady state, and
  returned the expected `/healthz` response. **Passed.**
- A saved plan can update the workload and demonstrate recovery from a failed
  revision. **Not tested in this cost-bounded run.**
- A reviewed saved destroy plan removed all 15 Terraform-managed test
  resources. Independent AWS reads and empty local Terraform state confirm no
  running workload, VPC, load balancer, image repository, role, or log group.
  AWS retains inactive service and stopped-task history plus an empty cluster.
- The hosted control plane and its state, runtime, queues, and API remain
  untouched. No hosted Nova apply or cross-account isolation is claimed.

## Acceptance status

Customer-side creation, live health, and Terraform teardown passed in account
`654654474502`; independent reads confirm no billable workload remains. The
ECS service is retained by AWS as `INACTIVE` history with zero tasks, and an
empty default cluster record remains. Update/recovery was not tested. This is
direct Terraform evidence, not a Nova-initiated apply; the hosted control plane
was untouched. On 2026-11-19, the goal owner accepted this isolated run as the
customer-side plan, apply, health, and teardown evidence for the general Nova
infrastructure goal. This acceptance substitutes for a hosted Nova run
under the required control-plane isolation; it does not establish Nova
generation, authorization, dispatch, cross-account isolation, or update and
recovery behavior.

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

Run a separately reviewed update/recovery test only if required by the accepted
customer-side lifecycle scope. No hosted Nova apply was attempted, and no Nova
customer workload is claimed as applied or certified.
