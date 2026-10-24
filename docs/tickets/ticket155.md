# ticket155 — Permit bounded reconciliation tags on owned customer resources

PR: Pending
Branch: `fix/customer-execution-reconciliation-tag-permissions`

## Problem / goal

The guarded customer foundation apply failed while reconciling ownership tags on already-created
customer resources. Its role allowed tag requests only when every ownership tag was supplied in the
request; Terraform updates existing tags incrementally.

## Current repo state

The customer CloudFormation role template has a request-tag-only grant and uses the obsolete
`logs:TagLogGroup` action. The first authenticated foundation apply therefore stopped before
Terraform outputs or service resources could be observed.

## Research / references used

- The failed CodeBuild execution record and CloudWatch log identified the three denied tag actions.
- The current inline policy on the connection-scoped execution role.
- AWS CloudFormation template validation.

## Work planned for the PR

- Correct the CloudWatch Logs tagging action to `logs:TagResource`.
- Permit tag reconciliation only when the target already carries this connection's two ownership
  tags.
- Retain the request-tag guard for newly created resources and all existing delete guards.

## Acceptance criteria

- [ ] The CloudFormation template validates.
- [ ] Existing owned VPC, ECR, App Runner, and log resources can receive bounded tag updates.
- [ ] Resources without both davdeploy ownership tags remain outside the reconciliation grant.
- [ ] Tests and CI pass.

## Acceptance status

Implementation and local validation complete; CI and the reviewed CloudFormation update are pending.

## Tests / validation performed

- Focused customer cloud lifecycle and connection-template tests.
- CloudFormation template validation in `us-east-1`.
- `git diff --check`.

## Boundaries

This changes IAM permissions only for resources already tagged `ManagedBy=davdeploy` and with the
current connection ID. It does not delete resources or enable a destroy operation.

## Evidence files produced

- `docs/test/test155.md`

## Follow-up work

After the reviewed policy update, update the existing customer connection stack and run a fresh
guarded plan before a single foundation retry.
