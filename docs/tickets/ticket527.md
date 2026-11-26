# ticket527 — Add fail-closed plan-scoped permissions for ECS Express

PR: #527 (draft; implementation package)
Branch: `feat/ecs-express-plan-scope-527`
Base: PR #526 (`docs/ecs-express-iam-boundary-526`)

## Goal

Implement deterministic permission-policy generation for the exact ECS Express pilot Terraform plan, without enabling its renderer or making cloud calls. The policy must bind to trusted plan data, scope actions and resources, include only exact connection-scoped `iam:PassRole`, and reject any operation the code cannot safely scope.

## Current repository and dependency state

- Backend main is `a456b84aa17600daf2b2c0bfe51d3bddb67e59ba` (PR #522).
- PR #519 is the disabled ECS Express renderer; PR #525 adds the separately provisioned ECS service-role pair; PR #526 records the verified unbounded-role issue and the required security contract. All are open drafts.
- Existing `nova_apply_access.py` supports S3, SQS, and DynamoDB only. The pilot root also contains VPC, internet gateway, subnet, route table, route-table association, ECR, CloudWatch Logs, ECS Express and `iam:PassRole` operations.
- The current ECS runner assumes one role without an STS session policy. Its configured role may be the `administrator-pilot` role with AWS `AdministratorAccess`. The renderer remains disabled.
- No AWS, Terraform, hosted control-plane, state or lock mutation is in scope.

## Research and references

- PR #526: `docs/security/ECS_EXPRESS_EXECUTION_IAM.md` defines role separation, exact-plan policy binding, fail-closed behavior and service-role pass constraints.
- AWS [STS session policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-api.html).
- AWS [IAM policy evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html), including resource-based grants to role sessions.
- AWS service authorization references: [EC2](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonec2.html), [ECR](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonelasticcontainerregistry.html), [CloudWatch Logs](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazoncloudwatchlogs.html), [ECS](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonelasticcontainerservice.html), and [IAM](https://docs.aws.amazon.com/service-authorization/latest/reference/list_awsidentityandaccessmanagementiam.html). Validate exact action/resource/condition keys against current primary documentation before coding.

## Planned work

1. Map every Terraform resource/action in the current pilot root to AWS actions and resource/condition scope; do not add a profile until every action is safely bounded.
2. Add deterministic policy construction from the approved saved-plan JSON and the exact account, region, connection, project, task role and infrastructure role identities.
3. Bind canonical policy digest to the saved-plan digest and run authorization; reject unsupported resources/actions, unknown IDs, untagged creations, replacements that cannot be constrained, policy-size overflow and missing role evidence.
4. Restrict `iam:PassRole` to the two exact roles and verified service principals; reject role management actions.
5. Add unit tests for actions, ARNs, request/resource tag conditions, create/update/delete/replacement, policy digest, pass-role, malformed plans and every fail-closed path.
6. Do not wire credentials or enable the renderer in this package unless separation of plan/state/apply/observe credentials is proven as part of the same review. No cloud execution is allowed.

## Acceptance criteria

- [ ] A reviewed mapping covers every action/resource in the current ECS Express pilot root using current AWS documentation.
- [ ] Policy generation is deterministic and only accepts an exact supported saved plan with trusted account/region/project/role identities.
- [ ] `iam:PassRole` is limited to the exact ECS task execution and infrastructure roles with service conditions.
- [ ] Unsupported/unscopable plans, wildcard escalation, oversized policy, unknown action/resource, role drift, and identity mismatch fail closed.
- [ ] Regression tests cover all supported and rejected cases; no AWS credentials are required.
- [ ] The runner and renderer remain disabled; hosted control plane, customer resources, state and locks remain untouched.
- [ ] Focused tests, required full clean-room validation for authorization/lifecycle changes, docs conventions, diff checks and all final-head CI checks pass.
- [ ] Claims distinguish implemented source and local tests from AWS execution evidence.

## Validation and evidence

Validation is pending implementation. If no cloud workload is run, no `docs/test/test527.md` is required. If cloud testing becomes necessary, stop and obtain explicit authorization for an exact bounded experiment before any mutation, then add `docs/test/test527.md`.

## Boundaries and follow-up

- No Terraform apply/destroy, AWS role assumption, AWS resource mutation, hosted control-plane operation, state/lock access, renderer enablement or customer-workload claim.
- Preserve audit evidence and protected local files.
- This permission builder alone cannot make the runner executable. Follow-up must separately scope plan/state/apply/observe/image-publish identities, prevent role resource-policy escalation, verify IAM profile and policy simulation, and complete an authorized isolated lifecycle before enabling the renderer.
