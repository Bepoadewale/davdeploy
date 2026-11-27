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
- Pinned AWS provider v6.73.0 source for [`aws_ecs_express_gateway_service`](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/ecs/express_gateway_service.go), matching the pilot root lockfile.
- Pinned provider shared ECS lookup helper in [`service.go`](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/ecs/service.go) and generic ECS tag hooks in [`tags_gen.go`](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/ecs/tags_gen.go).

## Work planned for the PR

- Inspect the pilot Terraform resource inventory and current AWS service authorization references.
- Document EC2 relationship/tag scope, exact ECR/log-group resources, Terraform data-source reads, ECS Express composite API actions, and exact-role `iam:PassRole` requirements in `docs/security/ECS_EXPRESS_EXECUTION_IAM.md`.
- Verify the runner's existing staged flow: foundation plan/apply with the service disabled, image publication, then a separate service plan/apply after subnet IDs exist.
- Identify ECS Express API side effects that are not represented as Terraform-managed resources in the approved plan.
- Review the pinned provider's direct ECS API calls, shared service lookup, generic tag synchronization, and best-effort EC2 managed-security-group filter. Record the mapping and keep unverified policy tuples deferred.
- Keep permission code, credential wiring and cloud execution deferred wherever exact scoping is not proven.

## Acceptance criteria

- [x] Current AWS authorization references cover relevant service actions and condition keys.
- [x] ECS Express composite actions and the distinct ECS infrastructure-role responsibility are documented.
- [x] A single combined plan's computed-subnet limitation is explicit, and the existing staged runner flow is identified as a way to supply known subnet IDs to the later service plan.
- [x] No broad caller permission for ELB/Auto Scaling is inferred from ECS-managed side effects.
- [x] The pinned provider's direct ECS calls, `DescribeServices` existence helper, generic `ListTagsForResource`/`TagResource`/`UntagResource` hooks, steady-state deployment polling, and best-effort `DescribeSecurityGroups` helper are mapped.
- [x] AWS resource types and documented tag conditions for ECS service, deployment, and tag actions are recorded. Exact IAM simulation and create-time tag authorization remain follow-up implementation gates; no policy code is claimed by this documentation PR.
- [x] Renderer, hosted control plane, customer resources, state and locks remain untouched.
- [x] Prior-head GitHub CI run `45916136160` passed all seven checks on head `13b6c302`.

## Acceptance status

The pinned-provider call map and implementation blocker are recorded. This PR does not implement or enable ECS permissions. The pilot remains ineligible for any apply until the follow-up policy code, exact IAM simulation, role-profile verification, clean-room checks and later lifecycle gates pass.

## Tests / validation performed

- Prior head `13b6c302ab5a9ff55cba772b4af4c1dd890755c7`: GitHub Actions run `45916136160` passed all seven checks.
- Updated provider helper/tag map still requires current-head documentation checks and CI.
- No code tests apply to this documentation-only package. No cloud call, Terraform plan/apply/destroy, role assumption, or hosted control-plane operation was performed.

## Evidence files produced

- `docs/security/ECS_EXPRESS_EXECUTION_IAM.md` — sourced action map and remaining authorization questions.
- No `docs/test/test527.md`; no customer workload test was run.

## Boundaries

- No Terraform apply/destroy, AWS role assumption, AWS resource mutation, hosted control-plane operation, state/lock access, renderer enablement or customer-workload claim.
- Preserve audit evidence and protected local files.

## Follow-up work

Implement the tested plan-bound policy; verify exact IAM simulation for all supported resource/condition tuples and tag operations; bind foundation and service stages to separate approved plan digests and phase-specific identities; then pass clean-room and CI gates before any bounded AWS pilot.
