# ECS Express plan-bound apply policy

## Status

Design and implementation are **not complete**. The draft policy prototype
fails AWS STS's hard session-policy size limit and has not been pushed. No AWS
resources, hosted control-plane components, Terraform state, or locks were
changed.

## Why the first policy shape does not work

The existing Nova apply path passes a plan-derived inline policy to
`AssumeRole`. AWS limits the combined inline session-policy JSON and managed
policy ARNs to 2,048 characters, and does not offer a quota increase. A local
prototype based on the pinned provider operation map measured 3,104 characters
for ECS Express create and 2,195 for the tested update. The existing code
correctly rejects oversize policies. Do not raise or bypass that limit.

The create operation is composite: in addition to the service action, AWS lists
cluster, gateway, task-definition, tagging, association, and role-passing
permissions. The plan policy must account for these dependencies while the
provider also makes read calls. A resource list that merely fits the size
limit is not sufficient: every action, supported resource type, condition key,
and provider call must match current AWS authorization behavior.

AWS also documents that ECS does not support resource-based policies. That
matters to the size failure: the explicit `Deny`/`NotResource` statement in the
shared S3/SQS/DynamoDB session-policy builder is unnecessary for an ECS-only
session. Keep that defense in shared profiles where it is needed; do not copy
it into the ECS policy. A compact ECS session policy can limit the action set,
while the verified fixed apply-role policy enforces exact resource, tag,
subnet, CPU/memory, cluster, and `iam:PassRole` boundaries. This is only a
candidate until its policy stays below STS's hard limit and IAM simulation
proves the full condition context.

A local size check of an action-only session-policy shape using the current
provider-call map measured 424 compact-JSON characters for create, 404 for
update, and 288 for delete. Those counts show that the STS limit is no longer
the blocker for this shape; they do not validate the action list or role
conditions. The fixed role allow rules must remain resource-scoped. IAM
simulation must evaluate each action against the required resource tuple and
derived context, including both resource types for multi-resource actions.

AWS states that ECS supports identity-based policies, does not support
resource-based policies, and supports tag-based access control. AWS STS session
tags become `aws:PrincipalTag` values on subsequent requests. This makes a
role-policy design using validated, short-lived session attributes a candidate
for keeping per-plan permissions bounded without placing every value in the
2,048-character inline policy.

## Proposed authorization architecture

Keep Nova's existing exact saved-plan approval and separate execution
authorization. For this ECS profile:

1. Parse the exact saved Terraform plan and validate the one supported ECS
   Express service resource, action, deterministic service name, account,
   region, cluster, known subnet IDs, CPU/memory, image digest, service roles,
   required ownership tags, and plan digest.
2. Derive a small fixed set of session tags from those validated values, such
   as `ProjectId`, `ServiceName`, `PlanDigest`, and the two approved subnet IDs.
   Do not accept caller-supplied tag values. Bind the tags to the immutable
   plan artifact and its digest.
3. Update the dedicated apply-role trust policy with a separate
   `sts:TagSession` permission. Restrict `aws:TagKeys` to the reviewed set and
   explicitly disallow keys that could override immutable role tags such as
   `ConnectionId`, `ManagedBy`, or the role-profile version.
4. Express the role's ECS maximum permissions with exact service actions,
   resource patterns, `iam:PassRole` ARNs and principals, and IAM conditions
   that compare resource/request tags with the session's `aws:PrincipalTag`
   values. Keep foundation, ECR publishing, EC2 networking, load balancer,
   autoscaling, observation, Terraform state, and control-plane permissions
   outside this role profile.
5. Pass a compact session policy containing only the plan-required actions.
   The fixed ECS role policy provides the resource/tag boundary; the session
   policy intersects it and narrows the actions for this exact plan. Omit the
   shared builder's `NotResource` statement only because ECS does not support
   resource-based policies. Retain the 2,048-character hard check and fail
   closed on overflow.
6. Verify the exact trust policy, role tags, inline policy and effective
   action/resource/tag combinations before issuing credentials. Extend IAM
   simulation to use the same derived principal-tag context and reject missing
   context, implicit denies, unexpected allows, or role drift. Include all
   resource types together for actions that require multi-resource checks.
7. Record the profile version, plan-policy digest, derived session-tag digest,
   role-profile digest and resulting audit evidence. The worker must receive
   only the approved saved plan and credentials derived for it.

Session tags are authorization inputs, not ordinary metadata. AWS documents
that session tags can override matching role tags, so the trust policy must
forbid tag keys that overlap fixed role-ownership tags. Only the trusted
backend may compute/pass the allowed dynamic tags, and their values must come
from the validated saved plan, never from Nova text or a customer request
outside that plan.

Before implementation, verify each ECS action/resource combination against
the current [AWS ECS service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html)
and the [pinned AWS provider v6.73.0 resource implementation](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/ecs/express_gateway_service.go).
In particular, determine whether provider tag reads need an unscoped read-only
permission, and whether `DescribeServiceDeployments` requires both service and
deployment resource ARNs. Reject a call pattern if it cannot be bounded as
required; do not infer safety from a successful IAM simulation alone.

## Migration strategy

1. Implement the new policy and session-tag construction behind a new apply
   role-profile version. Keep ECS renderer dispatch disabled.
2. Add contract, artifact-integrity, trust-policy, role-profile, IAM
   simulation, credential-issuance, and saved-plan worker tests. Verify that
   create, update, and destroy get distinct actions and that service roles are
   passed only to their documented service principals.
3. Validate the CloudFormation template and generated role policy together.
   Existing role profiles must fail closed when they do not match the new
   version; do not silently treat v2/v3 roles as upgraded.
4. Complete the repository's required clean-room authorization/Terraform
   validation. Open a separate, cost-bounded cloud lifecycle gate only after
   source checks pass and all exact target, authorization, and cleanup evidence
   has been reviewed. No live role or workload migration is part of this
   source-only package.
5. Retain rollback to the prior plan-only/apply-disabled behavior. Never enable
   the renderer or automatically modify customer roles as a side effect of
   merging this design.

## Trade-offs and limits

- **Benefit:** the dynamic resource scope moves into a fixed, inspected role
  policy, allowing the STS session policy to stay below its hard size limit.
- **Size rationale:** because ECS does not support resource-based policies,
  an ECS-only session does not need the shared builder's `NotResource` guard.
  The fixed role policy remains the resource and tag ceiling; the compact
  session policy intersects it to limit allowed actions. This does not make
  `Resource: "*"` acceptable in the fixed ECS allow rules.
- **Risk:** trust policy and role policy become more complex. Incorrect session
  tag values or overlapping keys could widen access; strict key allowlists,
  role-profile verification, deterministic tag derivation and negative tests
  are mandatory.
- **Auditability:** session tags appear in the STS request context and
  CloudTrail, but the plan artifact must still record their exact values and
  digest so an operator can connect credentials to the approved plan.
- **Compatibility:** changing trust and policy versions causes existing
  customer role profiles to fail closed until they are explicitly updated.
  This PR must not deploy those updates.
- **Coverage:** this is only the ECS Express service phase. It does not
  authorize foundation resources or prove end-to-end Nova execution, readiness,
  recovery, or teardown.

## Acceptance criteria

- [ ] Only the exact staged ECS service plan is supported; foundation or mixed
  managed-resource changes, replacements, unknown values, wrong subnets,
  wrong roles, and invalid tags are rejected.
- [ ] Create, in-place update, and separately approved destroy have distinct,
  minimal action sets and exact service-role boundaries.
- [ ] STS session tags are derived from the saved plan, key-allowlisted in the
  role trust, digest-bound to the plan artifact, and cannot override fixed
  ownership tags.
- [ ] The static role policy, compact session policy, IAM simulation, credential
  issuance, and saved-plan worker enforce one consistent scope.
- [ ] Tests cover supported and denied policy combinations, tag/session
  binding, IAM condition context, policy and token limits, and policy/role
  drift.
- [ ] Required clean-room validation and final-head CI pass. The renderer stays
  disabled until later lifecycle gates pass.
- [ ] No cloud workload, customer deployment, or Nova certification is claimed
  by this source/design package.
