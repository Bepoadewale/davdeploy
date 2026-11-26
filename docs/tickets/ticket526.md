# ticket526 — Review ECS Express customer execution permissions

PR: #526  
Branch: `docs/ecs-express-iam-boundary-526`  
Base: PR #525 (`feat/ecs-express-runner-iam-525`)

## Problem / goal

The default-off ECS Express runner is not ready for any customer-side apply.
Its shell runner assumes `DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN` for planning,
apply, observation, cleanup, and other operations without an STS session
policy. The supported customer connection template can create that role with
the AWS-managed `AdministratorAccess` policy. Connection verification only
checks that the role can be assumed and returns the expected account; it does
not inspect its effective permissions.

This review records the concrete permission gap and defines the least-privilege
architecture required before the renderer can run. It does not enable the
renderer or execute any AWS operation.

## Current repo state

- Backend `main` is `a456b84aa17600daf2b2c0bfe51d3bddb67e59ba` (merged PR #522).
- PR #519 is an open draft at `00697d7b6b84ed7d0ff0fef7effb7cf0037392e7`; its
  seven final-head checks passed in run `45903656967`.
- PR #524 is an open documentation draft at
  `75841d3ac80e8020b1b616fef07055167a8381c6`; all seven checks passed in run
  `45907870966`.
- PR #525 is an open draft at `bf876fe155a7fe946a457b6d61d74c25696893e0`; its
  seven final-head checks passed in run `45907548159`.
- No Terraform operation, customer AWS mutation, or hosted-control-plane
  mutation is part of this review.

## Verified findings

- `scripts/customer-workload-ecs-express-pilot.sh` assumes the configured
  customer execution role without the STS `Policy` parameter, then uses that
  session for every Terraform operation.
- `infrastructure/cloudformation/customer-discovery-role.yaml` attaches
  `arn:aws:iam::aws:policy/AdministratorAccess` to the connection-scoped
  `davdeployExecution-${ConnectionId}` role when `AccessMode` is
  `administrator-pilot`.
- `StsAwsDiscovery.verify_execution_role` calls `AssumeRole` without a session
  policy and checks only the returned account identity. It does not attest the
  role's inline policies, managed policies, permissions boundary, resource
  policies, or service control policies.
- The existing `nova_apply_access.py` plan-scoped policy profiles support
  S3, SQS, and DynamoDB resources. The ECS Express pilot root also changes EC2
  VPC/network resources, ECR, CloudWatch Logs, ECS Express services, and passes
  the connection-scoped task and infrastructure roles. The existing policy
  profile therefore cannot safely authorize this root.
- PR #525 provisions and verifies the two ECS service roles. It does not
  change the execution role used by the runner or provide permission isolation.

## Research / references used

- AWS [STS role sessions and session policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-api.html): an inline session policy limits the assumed role's identity-based permissions by intersection; it cannot grant additional permissions.
- AWS [policy evaluation guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html): a same-account resource policy that grants directly to an assumed-role session can bypass an implicit session-policy deny; the design must account for this case.
- AWS [ECS service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html): ECS Express create/update/delete actions and their resource/condition keys; create/update also require `iam:PassRole` for the ECS service roles.
- AWS [ECS Gateway permission troubleshooting](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/gateway-troubleshooting.html): caller permissions and the ECS infrastructure role are separate permission paths; `iam:PassRole` must identify the exact role.
- [Nova apply policy builder](../../apps/api/src/davdeploy/nova_apply_access.py) — the current supported plan-scoped resource profiles.

## Work planned for the PR

1. Document the existing ECS Express role-assumption flow and the verified
   `AdministratorAccess` path.
2. Define separate permission roles for planning, state access, apply/destroy,
   observation, and image publishing; do not use the administrator-pilot role
   as a customer workload credential.
3. Define the ECS Express apply-policy contract: the exact supported Terraform
   resource inventory; operation-specific actions; customer/account/region and
   project scoping; and `iam:PassRole` restricted to the two connection-scoped
   roles with `iam:PassedToService` conditions for ECS.
4. Specify how remote state and locking are scoped separately from the AWS
   provider permissions, and how each permission profile binds to the exact
   saved-plan digest and explicit approval.
5. Specify fail-closed checks for unsupported resources, unscopable IDs,
   oversized STS policies, unverified role drift, and policy-simulation
   mismatches. Include the session-policy/resource-policy caveat above.
6. Keep all customer execution disabled; no AWS role or resource is created,
   changed, or deleted by this review.

## Acceptance criteria

- [ ] The actual runner credential path and current `AdministratorAccess`
  grant are documented with source references.
- [ ] Role responsibilities remain separate for planning, state, apply or
  destroy, observation, and image publishing.
- [ ] The proposed apply policy binds only supported resource changes from the
  exact approved plan, and binds its policy digest to that plan and approval.
- [ ] `iam:PassRole` is limited to exact connection-scoped task and
  infrastructure role ARNs and the documented ECS service principals.
- [ ] Unsupported resources, actions, unscopable identities, oversized
  policies, missing role-profile evidence, and simulation mismatches fail
  closed.
- [ ] The design does not rely only on implicit session-policy denies where a
  resource policy may grant directly to the role session.
- [ ] The customer runner, renderer, and hosted control plane remain disabled
  or unchanged; no AWS mutation is performed.
- [ ] Documentation conventions, `git diff --check`, and all final-head CI
  checks pass.

## Acceptance status

This ticket records a security review and implementation contract only. The
least-privilege runner, plan-scoped ECS policy, IAM simulation, and isolated
workload cycle remain unimplemented. The renderer must stay disabled until the
follow-up implementation package passes its acceptance gates.

## Validation plan

- `GITHUB_PR_NUMBER=526 python3 scripts/check_doc_conventions.py`
- `git diff --check`
- All seven final-head GitHub Actions checks.
- No cloud validation is in scope for this documentation review.

## Tests / validation performed

- `GITHUB_PR_NUMBER=526 python3 scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- Final-head GitHub Actions checks are pending.

## Boundaries

- Do not use `AdministratorAccess` as the ECS customer workload credential.
- Do not mutate the hosted control plane, Terraform state, lock resources, or
  customer AWS resources.
- Do not claim that the existing Nova apply policy supports ECS Express.
- Preserve the protected untracked `--only-show-errors`, `.venv-pr399/`, and
  all retained audit evidence.

## Evidence files produced

No `docs/test/test526.md` is required; this package performs no customer
workload test or cloud mutation.

## Follow-up work

Implement the separate plan/state/apply/observation permission path, extend
the deterministic plan-scoped policy for the exact ECS Express root, verify
the effective role profile and `iam:PassRole` conditions, and run its complete
authorized lifecycle only after the execution and cost gates are approved.
