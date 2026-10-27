# ticket182 — Cognito email KMS deployment permission

PR: [#182 — Allow Terraform to manage Cognito email key](https://github.com/Bepoadewale/davdeploy/pull/182)
Branch: `fix/terraform-cognito-email-kms-permission`

## Problem / goal

Allow the protected Terraform apply role to create and manage the KMS key required by the reviewed Cognito custom-email sender.

## Current repo state

The Cognito Resend delivery plan is valid, but its protected apply failed because the Terraform role has no `kms:TagResource` or KMS-key creation permission. It created only the sender log group and IAM role before stopping; Terraform recorded that partial state.

## Research / references used

- Protected Terraform apply error from the reviewed Cognito Resend delivery plan.
- Existing `terraform-operations-bootstrap` least-privilege policy model.
- AWS Cognito custom sender requirement for a customer-managed KMS key and grant.

## Work planned for the PR

- Permit creation only of Terraform-tagged DavDeploy KMS keys.
- Permit the role to manage only KMS keys tagged as DavDeploy and aliases named `davdeploy-*`.

## Acceptance criteria

- [x] The apply role can create and manage the required tagged key, grant, rotation, deletion lifecycle, and alias.
- [x] The role cannot use this statement to manage untagged/non-DavDeploy keys.
- [ ] A reviewed Terraform apply completes the previously failed delivery deployment.

## Acceptance status

Implemented and statically validated; pending CI, bootstrap-policy deployment, and retry of the Cognito delivery apply.

## Tests / validation performed

`terraform fmt -check` and `terraform validate` for the operations-bootstrap root are recorded in the PR CI result.

## Evidence files produced

None. This is a deployment-permission correction; it does not run a customer workload.

## Boundaries

No customer workload, account, email content, token, or cloud execution permission is changed. The policy applies only to control-plane KMS resources.

## Follow-up work

Apply this bootstrap-policy change, rerun the saved Cognito email sender deployment, and complete live email OTP verification.
