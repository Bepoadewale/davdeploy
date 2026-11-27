# ticket529 — Add a plan-bound ECS Express service apply policy

PR: #529 (draft; stacked on PR #527)
Branch: `feat/ecs-express-apply-policy-529`
Base: PR #527 (`feat/ecs-express-plan-scope-527`)

## Problem / goal

The Nova exact-plan apply pipeline already derives an STS session policy from a
saved Terraform plan, verifies the dedicated apply-role profile, and applies
only the approved saved plan. Its supported resource policies do not yet cover
the ECS Express service phase. Add a narrowly scoped policy profile for the
existing staged ECS Express pilot so Nova can authorize that phase without
using the `administrator-pilot` role. Keep foundation provisioning, unknown
ECS side effects, and the renderer gated until they have separate reviewed
profiles and lifecycle evidence.

The first inline-policy design is not viable: the local prototype exceeded
AWS's fixed STS policy input limit. This PR remains a draft while the role
profile is redesigned around plan-derived, allowlisted STS session tags and
tag-conditioned role permissions. Do not relax the size limit or broaden the
customer apply role to make the prototype fit.

## Current repo state

- PR #527 is an open draft based on PR #526. It maps the ECS Express
  authorization surface and now records the direct API calls in the pinned
  AWS provider v6.73.0 source. Shared-helper, tag synchronization, and some
  condition/resource details remain open.
- `apps/api/src/davdeploy/nova_apply_access.py` creates session policies for
  S3, SQS, and DynamoDB plan changes and rejects unsupported resource types.
- `apps/api/src/davdeploy/generated_terraform_plan.py` stores the policy with
  the generated plan artifact. The credential endpoint verifies the policy
  digest, target, dedicated customer role profile, and IAM simulation before
  issuing short-lived credentials. The CodeBuild apply worker consumes those
  credentials only for the exact saved plan.
- The ECS pilot Terraform root uses a staged flow: create/apply the foundation
  with `enable_service=false`, then plan the service after subnets exist. This
  PR covers only a plan whose managed mutation is the exact ECS service
  resource; it does not authorize the foundation root or direct shell runner.
- A local prototype produced a 3,104-character create session policy and a
  2,195-character update policy. Both exceed the documented 2,048-character
  STS limit. The policy builder rejected them as intended. The prototype was
  not retained as source and no live role or resource was changed.
- Current AWS documentation confirms ECS does not support resource-based
  policies. A follow-up local size check of a compact action-only session
  policy measured 424 characters for create, 404 for update, and 288 for
  delete. This is only a candidate: no fixed role policy with exact resources
  and conditions has been implemented or IAM-simulated, so the candidate is
  not executable or approved.
- No AWS resource, hosted control-plane runtime, Terraform state, or lock is
  changed by this source package.

## Research / references used

- PR #527: [`ECS_EXPRESS_EXECUTION_IAM.md`](../security/ECS_EXPRESS_EXECUTION_IAM.md)
  and its pinned provider operation map.
- HashiCorp AWS provider v6.73.0
  [`ecs_express_gateway_service.go`](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/ecs/express_gateway_service.go).
- AWS [ECS action, resource, and condition reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html).
- AWS [CreateExpressGatewayService API](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_CreateExpressGatewayService.html),
  [UpdateExpressGatewayService API](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_UpdateExpressGatewayService.html),
  and [DeleteExpressGatewayService API](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_DeleteExpressGatewayService.html).
- AWS [STS session policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-api.html)
  and [IAM policy evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html).
- AWS [STS session tags](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_session-tags.html)
  and [IAM policy variables](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_variables.html).
- AWS [ECS IAM behavior](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security_iam_service-with-iam.html): ECS does not support resource-based policies; its documented identity-based and tag-based controls must define the caller boundary.

## Work planned for the PR

1. Finalize the tag-conditioned role-policy design in
   [`ECS_EXPRESS_APPLY_POLICY.md`](../security/ECS_EXPRESS_APPLY_POLICY.md).
   Derive all dynamic values from the validated saved plan; use a short,
   allowlisted STS session-tag set and a compact action-only session policy.
2. Bind `iam:PassRole` to the exact connection-scoped task execution and
   infrastructure roles and their respective `iam:PassedToService` values.
3. Add only the provider and AWS dependent actions needed for this staged
   service operation. Do not grant caller-side ELB, Auto Scaling, EC2 network,
   IAM role-management, image-push, state, observation, or broad wildcard
   permissions as a consequence of ECS-managed side effects.
4. Extend the dedicated apply-role trust, maximum policy, role-profile
   verification, IAM simulation context, artifact digest, credential issuance,
   and saved-plan apply contract together. Keep fixed ownership tags immutable
   and reject missing or unexpected session-tag context.
5. Reject unknown or unsupported plan attributes/actions, unknown subnet IDs,
   role ARNs outside the connection profile, replacements, missing tag
   conditions, and policies over the STS size limit.
6. Add deterministic regression tests for create, update, and destroy plans,
   exact ARNs and conditions, role passing, malformed/unsupported plans, tag
   and policy digest binding, IAM simulation, and size limits.
7. Keep customer dispatch disabled and run no cloud workload. Record the local
   focused tests, clean-room requirements, and final-head CI truthfully.

## Acceptance criteria

- [ ] The supported profile accepts only a saved plan for the staged ECS
  service resource and rejects foundation mutations or additional managed
  resources.
- [ ] Create, in-place update, and separately approved destroy policies contain
  only the pinned provider/AWS actions, exact service and role scope, trusted
  subnet/CPU/memory constraints, and required ownership/plan tags.
- [ ] `iam:PassRole` permits only the two exact connection-scoped roles with
  their respective documented service principals.
- [ ] The fixed apply-role ceiling, role-profile verification, IAM simulation,
  policy digest, credential issuance, and saved-plan apply contract agree on
  the same policy version and scope.
- [ ] Unknown IDs, unverified dependent actions, replacements, unsupported
  changes, missing constraints, role drift, and STS policy-size overflow fail
  closed.
- [ ] Focused tests and the required full local clean-room cycle pass without
  touching hosted control-plane resources or existing user artifacts.
- [ ] Final-head CI passes; the PR remains draft until review and the next
  lifecycle gates are met.
- [ ] No cloud workload, customer dispatch, or deployment is claimed.

## Acceptance status

Design remains incomplete and implementation has not started. The first
full session-policy prototype failed the size gate. A smaller action-only
session-policy shape fits the character bound in a local measurement, but its
fixed resource/tag-conditioned role policy and IAM simulation are unimplemented.
Neither result is a supported ECS apply profile. Even after this PR is
accepted, it will not by itself make the ECS renderer eligible for customer
execution: foundation permissions, phase-specific identity selection,
complete role/effective-
permission review, cost approval, and an authorized isolated Nova
plan/apply/update/recovery/destroy cycle remain separate gates.

## Tests / validation performed

- Local exploratory prototype command:
  `PYTHONPATH=apps/api/src /Users/adewale/Projects/davdeploy/.venv/bin/python -m pytest tests/test_nova_apply_access.py tests/test_nova_apply_role_profile.py -q`
  — 35 passed, 3 failed. The failures included create/update policy sizes
  above the STS limit and a replacement error-message assertion. The prototype
  source was restored; the test result is not evidence of a passing
  implementation.
- No Terraform command, cloud role assumption, AWS mutation, hosted
  control-plane access, or customer workload test was run.
- No AWS call, role assumption, apply, destroy, or hosted-control-plane access
  was performed.
- Final-head GitHub Actions run `45921934415` passed all seven checks on
  commit `02885d95` after the compact-policy design update.

## Boundaries

- Do not modify live AWS resources, the hosted control plane, Terraform state,
  or lock resources.
- Do not enable the renderer, use `AdministratorAccess` for customer workload
  execution, or infer permission to create/delete resources from policy tests.
- Preserve protected untracked files, audit artifacts, and existing worktrees.
- Do not claim direct AWS evidence as Nova dispatch or customer certification.

## Evidence files produced

- No `docs/test/test529.md`; this package performs no customer workload test.
- `docs/security/ECS_EXPRESS_APPLY_POLICY.md` records the confirmed limit,
  candidate architecture, migration approach, trade-offs, and acceptance
  criteria. It is design evidence only.

## Follow-up work

First complete the plan-tag-bound role-profile design and implementation.
Separately complete the foundation policy and phase credentials; finish the
provider helper/tagging authorization map; validate cost and customer revision
evidence; then pass the renderer's clean-room and explicitly authorized Nova
lifecycle gates before enabling dispatch.
