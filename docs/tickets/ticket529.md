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

## Work planned for the PR

1. Add a plan policy profile for the ECS Express service resource only, using
   the exact service name/cluster, known post-foundation subnet IDs, bounded
   CPU/memory, and required connection/project/plan tags from the trusted plan.
2. Bind `iam:PassRole` to the exact connection-scoped task execution and
   infrastructure roles and their respective `iam:PassedToService` values.
3. Add only the provider and AWS dependent actions needed for this staged
   service operation. Do not grant caller-side ELB, Auto Scaling, EC2 network,
   IAM role-management, image-push, state, observation, or broad wildcard
   permissions as a consequence of ECS-managed side effects.
4. Extend the dedicated apply-role maximum policy and role-profile verification
   consistently with the session policy; ensure IAM simulation checks every
   generated action/resource/condition tuple.
5. Reject unknown or unsupported plan attributes/actions, unknown subnet IDs,
   role ARNs outside the connection profile, replacements, missing tag
   conditions, and policies over the STS size limit.
6. Add deterministic regression tests for create, update, and destroy plans,
   exact ARNs and conditions, role passing, malformed/unsupported plans, policy
   digest binding, and size limits.
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

Implementation has not started. This ticket scopes a source-only authorization
package. Even if accepted, it will not by itself make the ECS renderer eligible
for customer execution: foundation permissions, phase-specific identity
selection, complete role/effective-permission review, cost approval, and an
authorized isolated Nova plan/apply/update/recovery/destroy cycle remain
separate gates.

## Tests / validation performed

- Bootstrap commit only; no code tests or Terraform commands have run for this
  PR.
- No AWS call, role assumption, apply, destroy, or hosted-control-plane access
  was performed.

## Boundaries

- Do not modify live AWS resources, the hosted control plane, Terraform state,
  or lock resources.
- Do not enable the renderer, use `AdministratorAccess` for customer workload
  execution, or infer permission to create/delete resources from policy tests.
- Preserve protected untracked files, audit artifacts, and existing worktrees.
- Do not claim direct AWS evidence as Nova dispatch or customer certification.

## Evidence files produced

- No `docs/test/test529.md`; this package performs no customer workload test.
- `docs/security/ECS_EXPRESS_APPLY_POLICY.md` will summarize the implemented
  contract and any remaining limitations.

## Follow-up work

Complete the foundation policy and separate phase credentials; finish the
provider helper/tagging authorization map; validate cost and customer revision
evidence; then pass the renderer's clean-room and explicitly authorized Nova
lifecycle gates before enabling dispatch.
