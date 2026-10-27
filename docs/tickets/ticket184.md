# ticket184 — Remove the unneeded Cognito email KMS alias

PR: [#184 — Remove unneeded Cognito email alias](https://github.com/Bepoadewale/davdeploy/pull/184)
Branch: `fix/remove-unneeded-cognito-email-alias`

## Problem / goal

Complete Cognito email delivery without expanding Terraform permissions for a KMS alias that the sender and Cognito user pool do not use.

## Current repo state

The protected apply created the tagged KMS key, sender Lambda, IAM role and policy, user-pool custom sender configuration, and invoke permission. It then stopped while creating an optional KMS alias because AWS evaluates alias and target-key authorization differently.

## Research / references used

- The protected apply AccessDenied result for `kms:CreateAlias`.
- The deployed configuration, which consistently references `aws_kms_key.cognito_email.arn`, not the optional alias.

## Work planned for the PR

- Remove the unused alias resource from the serverless control-plane configuration.
- Remove the corresponding unused Terraform-apply permission.

## Acceptance criteria

- [x] Cognito and the sender continue to use the tagged KMS key ARN directly.
- [ ] The protected delivery apply completes without creating an unnecessary alias.
- [ ] A live Cognito code is delivered through the sender.

## Acceptance status

Implemented locally; pending CI, merge, protected apply, and live delivery verification.

## Tests / validation performed

Terraform formatting and static validation are recorded in `docs/test/test184.md`.

## Evidence files produced

- `docs/test/test184.md`

## Boundaries

No customer account, email content, or cloud-execution authority changes. The change removes an uncreated optional alias and permission only.

## Follow-up work

Apply the reviewed serverless plan and request a new confirmation code for the controlled test account.
