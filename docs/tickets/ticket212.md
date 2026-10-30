# ticket212

PR: [#212](https://github.com/Bepoadewale/davdeploy/pull/212)

Branch: `security/finish-cloudtrail-edge`

## Problem / goal

Complete the restricted Terraform role permissions required for the reviewed
CloudTrail management-audit trail and make password plus TOTP the only Cognito
authentication path with a one-day refresh period.

## Current repo state

The prior serverless apply updated Cognito but failed when its scoped role could
not create the CloudTrail S3 bucket.

## Research / references used

- AWS IAM action references for S3 and CloudTrail.
- AWS Cognito MFA and token-validity documentation.

## Work planned for the PR

Grant only the named audit-bucket and CloudTrail lifecycle actions to the
Terraform apply role, require Cognito software-token MFA, and reduce refresh
token validity to one day.

## Acceptance criteria

- [x] Role can manage only the named DavDeploy audit bucket and trail.
- [x] Cognito excludes passwordless email OTP and requires software-token MFA.
- [x] Refresh tokens last one day.
- [ ] Bootstrap and serverless Terraform applies complete.

## Acceptance status

Code implementation is complete; deployment remains pending reviewed applies.

## Tests / validation performed

Pending Terraform validation.

## Evidence files produced

`docs/test/test212.md` will record the result.

## Boundaries

No broad S3 permission is granted. The bucket name is fixed to this account and
region. Passwordless email OTP is intentionally removed.

## Follow-up work

Run a controlled new-account, TOTP enrolment, sign-in, refresh, and sign-out journey.
