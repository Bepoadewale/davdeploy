# ticket326 — Add a customer-side Nova plan-only role

PR: #326 (draft)
Branch: `feat/customer-nova-plan-role-326`

## Problem / goal

Add an explicit customer AWS role for Nova's hosted Terraform plan path. The role must be distinct from deployment execution access, use the existing per-connection ExternalId trust, and have no ability to mutate customer resources.

## Current repo state

- `customer-discovery-role.yaml` creates a read-only discovery role by default. Its optional `administrator-pilot` path creates an `AdministratorAccess` execution role.
- `CloudConnection` stores `discovery_role_arn` and `execution_role_arn`, but has no plan-role field.
- Connection verification assumes the discovery role and, when present, the execution role; it confirms account identity but does not evaluate effective role permissions.
- `GeneratedTerraformPlanRunner` is backend-free and has no apply/destroy method. Its current plan configuration uses only the trusted `aws_caller_identity` data source.
- The isolated Nova CodeBuild project and future plan-broker permissions are being handled separately. This PR must not change that infrastructure or grant AssumeRole to an existing executor.

## Research / references

- `infrastructure/cloudformation/customer-discovery-role.yaml`
- `apps/api/src/davdeploy/domain.py`, `main.py`, `service.py`, `models.py`, and `integrations.py`
- `apps/api/src/davdeploy/generated_terraform_plan.py` and `generated_deployment_contract.py`
- `infrastructure/terraform/serverless-control-plane/main.tf` broker policy boundaries
- PR #324 isolated Nova CodeBuild boundary; PR #325 durable Nova plan request API

## Work planned

- Add a separate `plan_role_arn` purpose to the connection model and migration; keep it distinct from `execution_role_arn`.
- Add `plan-only` to Quick Create and the reviewed customer CloudFormation template, creating a role with a unique name, exact ExternalId trust, API and future isolated Nova plan broker principals, and explicit deny-all customer service permissions.
- Extend verification and connection detail output to report plan-role status accurately. Do not infer plan-only permissions for manually attached arbitrary role ARNs.
- Add focused tests and update customer connection/security documentation. Record required isolated broker AssumeRole permissions as follow-up work; do not modify the CodeBuild executor or PR #324 files.

## Acceptance criteria

- [ ] The `plan-only` role ARN is stored and returned separately from `execution_role_arn`.
- [ ] The plan-only template path creates no AdministratorAccess or other service Allow permissions, and includes an explicit service-action deny.
- [ ] Discovery and plan roles both require the exact connection ExternalId; the plan role trusts only the configured API and isolated Nova plan broker principals.
- [ ] Verification attempts the plan-role trust/account check and never reports a plan role verified from discovery-role success alone.
- [ ] Existing apply paths cannot use the plan role as execution access.
- [ ] Existing discovery and administrator-pilot contracts remain compatible.
- [ ] Focused tests pass; no AWS resources are created or changed.
- [ ] Required broker AssumeRole policy changes are documented as a follow-up and no existing executor policy is broadened here.

## Validation

Pending implementation. Validation will be local/static only; no AWS account changes or live STS role assumptions are in scope.

## Evidence

No customer workload evidence is expected because this PR performs no AWS workload run.

## Boundaries

No AdministratorAccess on the plan role, no Terraform apply/destroy, no AWS infrastructure changes, no change to PR #324 files, and no new AssumeRole permission on an existing executor in this PR.

## Follow-up work

Configure the isolated Nova plan broker ARN in the deployed control plane and grant that new broker only the required AssumeRole permission for `davdeployPlan-*`. Add the separate API verification broker permission needed to verify plan-role trust. Wire the plan request worker to assume this role and invoke only the fixed Nova plan method.
