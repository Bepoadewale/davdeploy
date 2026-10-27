# ticket181 — Cognito delivery through Resend

PR: [#181 — Deliver Cognito emails through Resend](https://github.com/Bepoadewale/davdeploy/pull/181)
Branch: `feat/resend-cognito-email-delivery`

## Problem / goal

Remove the SES sandbox recipient-verification requirement from Cognito sign-up and email-OTP sign-in delivery by using the verified Resend domain already used for workspace invitations.

## Current repo state

Cognito email delivery uses SES Developer mode. SES production access is denied, so unverified recipients cannot reliably receive sign-up and sign-in codes. Resend delivery for workspace invitations is configured with an SSM-held key.

## Research / references used

- AWS Cognito Custom Email Sender documentation: encrypted codes require a customer-managed KMS key and AWS Encryption SDK.
- Existing Resend invitation sender and runtime-only SSM key access.
- AWS pricing: customer-managed KMS key is $1/month; KMS includes 20,000 free requests/month; Resend Free permits 3,000 transactional emails/month and 100/day.

## Work planned for the PR

- Add a KMS-protected Cognito custom email sender Lambda.
- Deliver encrypted Cognito sign-up, resend, sign-in, and password-recovery codes through Resend.
- Give the sender only CloudWatch, KMS decrypt, and the existing Resend SSM parameter permissions.
- Attach the sender and KMS key to the existing Cognito user pool.

## Acceptance criteria

- [x] Cognito email events are sent through the verified Resend domain, not SES.
- [x] Codes are decrypted only in the sender Lambda and never logged.
- [x] The sender has least-privilege KMS and SSM access.
- [x] Focused unit and Terraform validation pass.

## Acceptance status

Implemented and locally validated; pending full CI, reviewed Terraform plan/apply, and live email verification.

## Tests / validation performed

`docs/test/test181.md` records the focused sender, lint, and Terraform validation. Full CI remains the merge gate.

## Evidence files produced

- `docs/test/test181.md`

## Boundaries

This changes only Cognito transactional email delivery. It does not expose credentials to the browser, enable workload execution, or alter authorization, workspace membership, invitations, or cloud access.

## Follow-up work

After deployment, test sign-up, sign-in, and password recovery to an unverified SES recipient; monitor Resend delivery/bounce events and remove the temporary SES-recipient workaround after confirmation.
