# ticket177 — Record active Cognito SES delivery configuration

PR: [#177](https://github.com/Bepoadewale/davdeploy/pull/177)
Branch: `docs/active-ses-cognito`

## Problem / goal

Current operational documentation described SES as a future option after Cognito was configured
with the verified `davdeploy.tech` SES identity for account and authentication email.

## Current repo state

Cognito uses the verified domain identity with `notify@davdeploy.tech`. Amazon SES remains in its
account sandbox pending AWS approval for transactional production sending. Resend continues to send
workspace invitations.

## Research / references used

- Live Cognito email configuration and SES identity/account status.
- Terraform plan and successful protected apply for the Cognito sender configuration.
- Existing email and deployment runbooks.

## Work planned for the PR

- Distinguish Cognito SES mail from the active Resend invitation path.
- Record the sandbox and production-access boundary truthfully.
- Document the bare-address constraint for Cognito From and Reply-To configuration.

## Acceptance criteria

- [x] Operators can identify the sender and recipient limitations before SES production approval.
- [x] Resend remains documented as the workspace-invitation sender.
- [x] Terraform secret descriptions match their active use.

## Acceptance status

Documentation is complete pending review.

## Tests / validation performed

- `python scripts/check_doc_conventions.py`
- Reviewed live Cognito email configuration and SES identity status.

## Evidence files produced

- Protected Terraform apply run `40369384272`.

## Boundaries

This documentation change does not change DNS, Cognito, SES, Resend, Cloudflare, or customer data.

## Follow-up work

After AWS grants SES production access, run and record the controlled Yahoo browser confirmation and
email-OTP journey.
