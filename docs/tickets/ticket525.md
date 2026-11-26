# ticket525 — Pre-provision ECS Express service roles

PR: #525  
Branch: `feat/ecs-express-runner-iam-525`  
Base: PR #519 (`feat/ecs-express-renderer-519`)

## Problem / goal

The ECS Express pilot Terraform root currently creates two IAM roles and
attaches AWS managed policies during the same customer workload apply. The
renderer is disabled, and the effective permissions of its customer execution
role have not been approved. A customer workload execution role should not
need permission to create arbitrary IAM roles or attach policies merely to
launch this fixed ECS Express profile.

This package moves the two ECS service roles to an explicit customer-side
CloudFormation bootstrap. Terraform consumes those exact connection-scoped
roles as data sources. The CloudFormation template is published through the
existing append-only, content-hash template host. This does not grant the
runner's customer execution role any new permission and does not enable the
renderer.

## Current repo state

- Backend `main` is `a456b84aa17600daf2b2c0bfe51d3bddb67e59ba`.
- PR #519 has a disabled ECS Express renderer and its final source head
  `00697d7b6b84ed7d0ff0fef7effb7cf0037392e7` passed all seven checks in run
  `45903656967`.
- PR #520's actual-plan policy and PR #522's price model are merged. The
  synthetic price correction is open as PR #524; no pricing result here is
  approval evidence.
- The Terraform root currently owns the task execution and ECS infrastructure
  roles. The runner's effective customer execution-role policy has not been
  independently reviewed.
- The user-authorized AWS account inventory found no ECS service in the default
  cluster and no `davdeploy-ecs-*` IAM role. The hosted control-plane stacks,
  runtime, state, and lock resources remain outside this package's scope.
- No Terraform operation is active in the local monitor registry.

## Research / references used

- [Amazon ECS Express Mode prerequisites](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-create-full.html)
  — an Express service requires a task execution role and an infrastructure
  role.
- [Create an Express Mode service using the AWS CLI](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html)
  — AWS specifies the task role's `ecs-tasks.amazonaws.com` trust and
  `AmazonECSTaskExecutionRolePolicy`, and the infrastructure role's
  `ecs.amazonaws.com` trust and
  `AmazonECSInfrastructureRoleforExpressGatewayServices` policy.
- [ECS infrastructure role and pass-role permission](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/infrastructure_IAM_role.html)
  — the infrastructure role is passed to ECS with
  `iam:PassedToService = ecs.amazonaws.com`.
- [IAM PassRole guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html)
  — `iam:PassRole` can be restricted to specific role ARNs and should only
  permit roles with intended permissions.
- [ECS service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html)
  — Express create/update actions require role passing for ECS and ECS tasks.
- [Append-only CloudFormation template publishing](../architecture/append-only-template-publishing.md)
  — newly published templates use content-hash keys and protected Terraform
  addresses.

## Work planned for the PR

1. Add a customer-side CloudFormation template that creates the two
   connection-scoped ECS Express service roles with exact AWS service trust
   principals, the AWS-documented managed policies, and explicit outputs.
2. Publish the template at a new content-hash S3 key using the existing
   append-only template publisher, without changing prior URLs or objects.
3. Replace Terraform-managed IAM roles and attachments with lookups of the
   exact connection-scoped roles; keep the renderer disabled.
4. Extend contract tests to reject role creation/attachment in this workload
   root, verify trust and policy ARNs, and verify template publication is
   append-only.
5. Document role-bootstrap, plan, workload destroy, and role-stack cleanup
   ordering. Do not run the customer CloudFormation template or any Terraform
   mutation in AWS in this PR.

## Acceptance criteria

- [ ] The published template creates only the exact ECS task execution and
  infrastructure roles for a validated DavDeploy connection identifier.
- [ ] Trust principals and AWS managed-policy ARNs match current AWS guidance.
- [ ] The Terraform workload root no longer creates IAM roles or attaches
  managed policies; it refers only to the two exact role names.
- [ ] A new template uses a unique source-content SHA-256 S3 key and a stable
  protected object address; existing template URLs remain unchanged.
- [ ] Regression tests cover malformed identifiers, wrong trust, wrong
  managed-policy ARNs, role-creation regressions, and append-only hosting.
- [ ] Documentation states the required bootstrap/teardown order and that
  pre-provisioning does not prove effective runner-role permissions.
- [ ] The ECS Express renderer remains disabled and no customer workload is
  applied or certified by this package.
- [ ] Focused tests, Terraform validation, documentation conventions,
  `git diff --check`, and all final-head CI checks pass.
- [ ] No AWS resources or hosted control-plane resources are mutated.

## Acceptance status

Implementation has not started. This ticket records the scoped change before
code work. This PR cannot satisfy the remaining effective-permission review,
approval-bound customer pricing, clean-room lifecycle, or authorized
remote-state execution gates.

## Tests / validation performed

- Read-only AWS identity and inventory checks were run for account
  `654654474502`, region `us-east-1`; no ECS service, pilot role, or active
  Terraform monitor run was found.
- Official AWS service, managed-policy, and IAM PassRole documentation was
  reviewed; references are listed above.
- No Terraform plan, apply, destroy, CloudFormation deployment, hosted
  control-plane mutation, or workload certification was performed.

## Boundaries

- Do not change or deploy the hosted control plane, runtime, Terraform state,
  or lock resources.
- Do not use `AdministratorAccess` as the customer execution credential.
- Do not grant the runner `iam:CreateRole` or managed-policy attachment rights
  as part of this package.
- Do not run the CloudFormation bootstrap or a paid customer workload without
  the existing exact, bounded execution manifest and cost/cleanup gates.
- Do not delete retained plans, evidence, worktrees, branches, lineage records,
  or resources without exact current approval.

## Evidence files produced

No `docs/test/test525.md` is required for this documentation and source-code
package because it performs no customer workload test or AWS mutation.

## Follow-up work

Review the exact permissions required by the runner's customer execution role
and its per-plan session policy, including `iam:PassRole` on these two role
ARNs with service conditions. Add an independent preflight that verifies the
roles' trust and policy attachments before planning. Then bind pricing to a
persisted customer revision and budget, pass clean-room and monitored remote
state lifecycle evidence, and obtain explicit authorization before any AWS
mutation. Keep the renderer disabled until all PR #519 gates are satisfied.
