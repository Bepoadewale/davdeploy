# ticket211

PR: [#211](https://github.com/Bepoadewale/davdeploy/pull/211)

Branch: `security/mfa-cloudtrail-edge`

## Problem / goal

Enable Cognito authenticator-app TOTP without SMS, create a low-cost management
audit trail, and make the public API reachable through a Cloudflare Worker with
an origin-secret guard.

## Current repo state

Email-code authentication remains the default passwordless path. Cognito does
not combine an enrolled TOTP factor with `EMAIL_OTP`; users who opt into TOTP
must use the explicitly enabled password-plus-authenticator path. No customer
secrets are committed. The Cloudflare token and origin secret are operational
configuration only.

## Research / references used

- AWS Cognito TOTP MFA documentation.
- AWS CloudTrail management-event and log-file validation documentation.
- Cloudflare Workers Free-plan limits and Workers Routes documentation.

## Work planned for the PR

Enable TOTP, an origin guard and Worker source, and management-event auditing.

## Acceptance criteria

- [x] Configure Cognito optional software-token MFA and password auth required by TOTP.
- [x] Add a secret-backed origin-header guard that is inactive until a configured SSM parameter exists.
- [x] Add a Free-plan Worker source and documented staged rollout.
- [x] Define versioned, private, SSE-S3 encrypted CloudTrail management-event storage with log-file validation.
- [x] Add focused guard tests and static Terraform contracts.
- [ ] Apply the reviewed Terraform plan and complete the documented edge rollout.

## Acceptance status

Implementation and local validation are complete. Deployment remains pending
the normal reviewed Terraform workflow and a Cloudflare Worker token with
Workers Scripts edit permission.

## Tests / validation performed

` .venv/bin/python -m pytest -q tests/test_serverless_runtime.py `: 31 passed.

## Evidence files produced

`docs/test/test211.md` records the local validation boundary.

## Boundaries

Email-code sign-in is retained. Cognito does not combine enrolled TOTP with
`EMAIL_OTP`; an enrolled user must use the password-plus-authenticator route.
The runtime token is retrieved from SSM and is never committed.

## Follow-up work

Deploy only after the plan is reviewed. Verify the Worker endpoint succeeds and
the direct API endpoint returns 403 before calling the edge guard active.
