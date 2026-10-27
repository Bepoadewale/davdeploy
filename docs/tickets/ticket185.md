# ticket185 — Record live Cognito authentication acceptance

PR: [#185 — Document live Cognito email authentication](https://github.com/Bepoadewale/davdeploy/pull/185)
Branch: `docs/live-cognito-auth-acceptance`

## Problem / goal

Reconcile authentication operations documentation with the deployed Cognito custom-email sender and record a controlled hosted identity acceptance.

## Current repo state

The hosted user pool invokes the Resend custom sender with a KMS-encrypted Cognito code. Older operations text still described SES sandbox delivery as the active authentication path.

## Research / references used

- Live Cognito confirmation and `EMAIL_OTP` challenges for a controlled test identity.
- Live custom-sender CloudWatch invocation records.
- Authenticated hosted API, CLI, and MCP requests.

## Work planned for the PR

- Correct the authentication-email operational runbook.
- Add non-sensitive acceptance evidence for the controlled hosted journey.

## Acceptance criteria

- [x] Documentation identifies Resend custom-sender delivery as the active Cognito path.
- [x] A newly confirmed identity can create a personal workspace and call the hosted API.
- [x] CLI and MCP can call the same hosted API with the same Cognito identity token.

## Acceptance status

Completed in the controlled test environment; browser interaction remains available through the same Cognito email-OTP journey.

## Tests / validation performed

Recorded in `docs/test/test185.md`.

## Evidence files produced

- `docs/test/test185.md`

## Boundaries

No customer cloud credential, workload execution, or authorization expansion occurred. Tokens, OTPs, email addresses, and workspace identifiers are excluded from evidence.

## Follow-up work

Run a human browser sign-in from `https://davdeploy.tech` using the controlled account, then extend the evidence only with non-sensitive outcome details.
