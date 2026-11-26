# ticket527 — Map the ECS Express plan permission boundary

PR: #527 (draft; sourced design review)
Branch: `feat/ecs-express-plan-scope-527`
Base: PR #526 (`docs/ecs-express-iam-boundary-526`)

## Problem / goal

Complete the AWS action, resource, and condition mapping needed before deterministic plan-scoped permission code can safely authorize the ECS Express pilot. Record verified composite API behavior and identify where the current root must be phased. Do not enable the renderer or make cloud calls.

## Current repo state

- Backend main is `a456b84aa17600daf2b2c0bfe51d3bddb67e59ba` (PR #522).
- PR #519 is the disabled ECS Express renderer; PR #525 adds the separately provisioned ECS service-role pair; PR #526 records the verified unbounded-role issue and the required security contract. These PRs remain open drafts.
- Existing `nova_apply_access.py` supports S3, SQS, and DynamoDB only. The ECS Express pilot root includes EC2 networking, ECR, CloudWatch Logs and an ECS Express API resource.
- The current runner assumes one role without an STS session policy. Its configured role may be the `administrator-pilot` role with AWS `AdministratorAccess`. The renderer remains disabled.
- No AWS, Terraform, hosted control-plane, state or lock mutation is in scope.

## Research / references used

- PR #526: `docs/security/ECS_EXPRESS_EXECUTION_IAM.md` records the runner flaw and required security contract.
- AWS [STS session policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-api.html).
- AWS [IAM policy evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html), including resource-based grants to role sessions.
- AWS service authorization references: [EC2](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html), [ECR](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecr.html), [CloudWatch Logs](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html), [ECS](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html), and [IAM](https://docs.aws.amazon.com/service-authorization/latest/reference/list_iam.html).
- ECS APIs: [CreateExpressGatewayService](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_CreateExpressGatewayService.html) and [DeleteExpressGatewayService](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_DeleteExpressGatewayService.html).

## Work planned for the PR

- Inspect the pilot Terraform resource inventory and current AWS service authorization references.
- Document EC2 relationship/tag scope, exact ECR/log-group resources, Terraform data-source reads, ECS Express composite API actions, and exact-role `iam:PassRole` requirements in `docs/security/ECS_EXPRESS_EXECUTION_IAM.md`.
- Verify the runner's existing staged flow: foundation plan/apply with the service disabled, image publication, then a separate service plan/apply after subnet IDs exist.
- Identify ECS Express API side effects that are not represented as Terraform-managed resources in the approved plan.
- Keep permission code, credential wiring and cloud execution deferred wherever exact scoping is not proven.

## Acceptance criteria

- [x] Current AWS authorization references cover relevant service actions and condition keys.
- [x] ECS Express composite actions and the distinct ECS infrastructure-role responsibility are documented.
- [x] A single combined plan's computed-subnet limitation is explicit, and the existing staged runner flow is identified as a way to supply known subnet IDs to the later service plan.
- [x] No broad caller permission for ELB/Auto Scaling is inferred from ECS-managed side effects.
- [ ] Every provider API call and internal ECS resource ARN is verified against the pinned provider and represented in tested policy code; deferred to a follow-up implementation package.
- [x] Renderer, hosted control plane, customer resources, state and locks remain untouched.
- [x] Final-head GitHub CI run `45911833917` passed all seven checks.

## Acceptance status

The sourced authorization mapping and implementation blocker are recorded. This PR does not implement or enable ECS permissions. The pilot remains ineligible for any apply until the deferred criteria and later lifecycle gates are met.

## Tests / validation performed

- `GITHUB_PR_NUMBER=527 python3 scripts/check_doc_conventions.py`: passed.
- Final-head GitHub Actions run `45911833917`: all seven checks passed.
- `git diff --check`: passed.
- No code tests apply to this documentation-only package. No cloud call, Terraform plan/apply/destroy, role assumption, or hosted control-plane operation was performed.

## Evidence files produced

- `docs/security/ECS_EXPRESS_EXECUTION_IAM.md` — sourced action map and remaining authorization questions.
- No `docs/test/test527.md`; no customer workload test was run.

## Boundaries

- No Terraform apply/destroy, AWS role assumption, AWS resource mutation, hosted control-plane operation, state/lock access, renderer enablement or customer-workload claim.
- Preserve audit evidence and protected local files.

## Follow-up work

Verify exact AWS provider API behavior and internal resource ARNs; bind the existing foundation and service stages to separate approved plan digests and phase-specific identities; implement tested plan-bound policy generation; then pass clean-room and CI gates before any bounded AWS pilot.
