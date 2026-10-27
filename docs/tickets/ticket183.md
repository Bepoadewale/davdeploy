# ticket183 — Cognito email KMS alias target permission

PR: [#183 — Permit Cognito email KMS alias target](https://github.com/Bepoadewale/davdeploy/pull/183)
Branch: `fix/cognito-email-kms-alias-key-permission`

## Problem / goal

Finish the Cognito Resend deployment by allowing the protected Terraform role to create the DavDeploy KMS alias against its tagged target key.

## Current repo state

The reviewed apply created the KMS key, sender Lambda, role, policy, user-pool trigger, and permission, then safely stopped because KMS authorizes `CreateAlias` against both alias and target-key ARNs.

## Research / references used

- Exact AWS KMS `CreateAlias` AccessDenied result from the protected apply.
- Existing tagged-key least-privilege policy introduced in PR #182.

## Work planned for the PR

- Add the target-key ARN to the existing DavDeploy alias permission, retaining the DavDeploy resource-tag condition.

## Acceptance criteria

- [x] The apply role can create the reviewed alias only against a tagged DavDeploy key.
- [ ] The Cognito Resend delivery apply completes.

## Acceptance status

Implemented; pending CI, bootstrap-policy deployment, and serverless apply retry.

## Tests / validation performed

Terraform formatting and static validation will run in CI.

## Evidence files produced

None. This permission correction does not execute a customer workload.

## Boundaries

No customer data, workload, email content, or cloud-execution authority changes.

## Follow-up work

Rerun the saved Cognito delivery plan and confirm an unverified SES recipient receives a Resend-delivered Cognito code.
