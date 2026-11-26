# ticket520 — Bound Nova ECS Express actual plans

PR: #520
Branch: `feat/ecs-express-plan-policy-520`

## Problem / goal

The checked-in actual-plan evaluator has no ECS Express-specific contract. A
new resource shape must not pass merely because its Terraform values look
plausible. Add deterministic checks that bind the bounded pilot service to its
same-plan image repository, execution and infrastructure roles, logs, and
project-scoped network. Unknown, unbound, or unsupported shapes must fail
closed.

This is a source-only policy package. It must not enable the renderer, customer
dispatch, or cloud execution. Cost completeness, execution-role IAM scope,
remote-state lifecycle, and Nova-originated execution remain separate gates.

## Current repo state

- Backend `main`: `dbbf7c135b7be97c832927d5c1758bc1faab805d` (merged PR #518).
- Draft PR #519 contains the disabled ECS Express pilot renderer and runner;
  its exact root is `infrastructure/terraform/customer-workload-ecs-express-pilot`.
- PR #519's broad planning profile `aws-ecs-fargate` intentionally does not
  resolve to the narrow single-container pilot renderer.
- The exact pilot root uses a public VPC with two public subnets. AWS documents
  that Express Mode enables public task IPs by default for public subnets; this
  is a material egress/security and cost boundary that the policy must expose.
- No AWS resources or hosted control-plane resources are changed by this PR.

## Research / references used

- AWS ECS Express resource provisioning and defaults:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html
- AWS ECS Express getting started and role requirements:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html
- AWS ECS infrastructure role and `iam:PassRole` guidance:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/infrastructure_IAM_role.html
- AWS ECS IAM and service-linked-role boundaries:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security_iam_service-with-iam.html
- HashiCorp AWS provider resource schema:
  https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_express_gateway_service
- Existing deterministic plan evaluator:
  `apps/api/src/davdeploy/generated_plan_policy.py`
- Existing pilot Terraform root:
  `infrastructure/terraform/customer-workload-ecs-express-pilot`

## Work planned

1. Add an exact ECS Express plan contract with strict resource inventory and
   same-plan reference binding for service, VPC/subnets, ECR, log group, and
   both IAM roles.
2. Deny unknown safety-relevant values, mutable or external image sources,
   task-role permissions, secrets, unbounded scaling, unexpected containers,
   unsupported network resources, cross-account role ARNs, and malformed
   service settings.
3. Review the two AWS-managed role policies and exact `iam:PassRole` service
   conditions; preserve human review where managed-policy contents cannot be
   evaluated from the plan.
4. Handle the pilot's `force_delete` ECR setting only for the exact linked test
   repository and retain destructive-change review.
5. Add regression tests for the valid narrow shape and each fail-closed case.
6. Keep pricing status incomplete for ECS Express until all billable supporting
   resources and usage assumptions have a separate verified regional model.
7. Keep customer execution disabled and record no cloud evidence.

## Acceptance criteria

- [ ] An ECS Express service is accepted only in the exact supported pilot
  inventory and with references bound to resources in the same plan.
- [ ] Required service attributes, immutable same-account/region ECR digest,
  one-task ceiling, health path, no task role, no secret injection, and log
  group are validated; unknown critical values are denied.
- [ ] Both roles have exact ECS service trust; only the two expected managed
  policies are reviewable; role passing is bound to the expected AWS service.
- [ ] The network is bound to the pilot VPC and exactly two approved public
  subnets; unsupported routes, endpoints, NAT, IPv6, and additional public
  resources fail closed. Public task IP exposure is explicitly recorded for
  human review.
- [ ] ECR force deletion is eligible only for the exact project repository
  linked to the pilot service and remains subject to destructive-change review.
- [ ] Unsupported plans remain denied or review-required; this policy does not
  mark the plan cost-complete or enable dispatch.
- [ ] Focused tests, full relevant CI checks, doc conventions, lint, and
  `git diff --check` pass.
- [ ] No AWS workload, hosted control plane, Terraform state, or lock resource
  is accessed or changed.

## Acceptance status

Implemented as a source-only actual-plan policy and regression tests. The draft
remains review-required: pricing, effective role permissions, Nova dispatch,
and a real provider-generated saved-plan fixture remain separate gates.

## Validation performed

- `tests/test_generated_plan_policy.py`: 642 passed.
- Ruff on the changed policy and test files: passed.
- `git diff --check`: passed.
- Synthetic policy tests verify the exact pilot inventory, ECR binding,
  fail-closed network binding, and that ECR force deletion requires the
  exact-pilot allowlist entry and remains reviewable.
- No AWS operations, Terraform plans, or hosted control-plane operations were
  run.
- Official AWS and HashiCorp documentation was reviewed as listed above.

## Boundaries

- Preserve the hosted control plane, runtime, state, and locks.
- Do not enable Nova execution or alter the current ECS Express renderer gate.
- Do not use direct ECS evidence as proof of Nova dispatch or cost completeness.
- Preserve the protected untracked `--only-show-errors`, `.venv-pr399/`, and
  retained SageMaker lineage evidence.

## Evidence files

- No `docs/test/test520.md` is required because this PR performs no customer
  workload test or cloud mutation.

## Follow-up

Complete the separate regional cost model, effective execution permission
review, isolated remote-state runner lifecycle, and hosted Nova authorization
path before considering any execution gate change.
