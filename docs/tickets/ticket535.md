# ticket535 — Preserve the ECS Express apply-policy design handoff

PR: #535 (draft; documentation-only replacement for closed PR #529)
Branch: `feat/ecs-express-apply-policy-534`
Base: PR #519 (`feat/ecs-express-renderer-519`)

## Problem / goal

Keep the ECS Express plan-bound apply-policy proposal and its unresolved AWS
authorization review available after PR #527 was merged into PR #526. GitHub
closed PR #529 when its base branch was deleted. This replacement carries
forward the design notes and adds the current sourced finding; it does not
implement or enable an ECS apply policy.

## Current repo state

- PR #527's pinned-provider action map is merged into PR #526 at merge commit
  `346b4a6bb4ac336df0c58c0695d5a54d8582bb13`; #526/#525 are subsequently
  merged only into the #519 feature branch, not `main`.
- PR #529 remains closed and unmerged. Its code prototype was restored; the
  replacement contains documentation only.
- The ECS Express renderer remains disabled. No cloud role or workload was
  changed, and no Terraform plan, apply, or destroy was run for this package.

## Research / references used

- AWS [ECS actions, resources, and condition keys](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html)
  documents the dependent actions for `CreateExpressGatewayService` and
  action-specific resource types and conditions.
- AWS [CreateExpressGatewayService API](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_CreateExpressGatewayService.html)
  describes the composite operation and its service behavior.
- The pinned AWS provider v6.73.0 operation map is in
  [`ECS_EXPRESS_EXECUTION_IAM.md`](../security/ECS_EXPRESS_EXECUTION_IAM.md).
- AWS IAM documents that same-account resource policies naming a role-session
  principal can grant access beyond an implicit session-policy deny. This is
  relevant because an ECS caller session can be named from other AWS service
  resource policies even though ECS resources themselves do not support such
  policies.
- The compact action-only policy's earlier character measurements omitted
  this explicit-deny boundary and do not prove that a complete safe session
  policy fits the STS input limit. No implementation is safe until this is
  resolved and tested.

## Work planned for the PR

- Preserve the original design and policy acceptance gates from closed PR
  #529, including the new cross-service resource-policy boundary blocker.
- Record the action/resource simulation gap found while reviewing the AWS
  authorization reference and role-session policy evaluation.
- Keep the documentation-only status explicit and request fresh CI on this
  replacement PR.

## Acceptance criteria

- [x] Preserve the compact session-policy candidate, migration strategy,
  trade-offs, and policy acceptance criteria in security documentation.
- [x] Record that each dependent ECS action requires its own exact
  resource/condition mapping; gateway association is scoped to the gateway and
  `ecs:cluster`, not simulated as a second cluster resource.
- [x] Correct the compact-session-policy proposal: ECS's lack of ECS resource
  policies does not justify removing the explicit deny boundary for
  cross-service resource-policy grants to the assumed role session.
- [x] Keep all implementation and cloud execution claims truthful; no ECS
  apply policy is supported by this documentation.
- [ ] Obtain final-head CI for this replacement PR.
- [ ] Keep the renderer disabled until action/resource mapping, role-profile
  verification, deterministic policy tests, and authorized lifecycle evidence
  meet their separate gates.

## Acceptance status

The replacement is documentation-only and remains a draft until its own
final-head CI passes. No policy implementation, cloud apply, or customer
workload execution is claimed.

## Tests / validation performed

The original documentation content passed all seven checks in GitHub Actions
run `45924552446` on former PR #529 head `803553159c501ce9ff0750354b62ecb518ecd0ba`.
That run does not validate this replacement branch; the new PR requires its own
final-head checks. No customer workload evidence file is added because this
package performed no workload test.

## Evidence files produced

- `docs/security/ECS_EXPRESS_APPLY_POLICY.md` — design and acceptance criteria.
- `docs/tickets/ticket529.md` — original policy design ticket, with its PR
  history corrected.
- `docs/tickets/ticket535.md` — replacement PR record.

## Boundaries

Do not modify the hosted control plane, customer roles, Terraform state, locks,
or AWS workloads. Continue to distinguish same-account direct lifecycle
evidence from Nova-originated execution.

## Follow-up work

Complete action/resource/condition mapping and deterministic policy tests,
then separately pass clean-room, authorization, and isolated lifecycle gates
before enabling the renderer.
