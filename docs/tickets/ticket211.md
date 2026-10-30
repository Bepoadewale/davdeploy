# Ticket 211: MFA, CloudTrail and API edge protection

## Goal

Enable Cognito authenticator-app TOTP without SMS, create a low-cost management
audit trail, and make the public API reachable through a Cloudflare Worker with
an origin-secret guard.

## Current state and boundary

Email-code authentication remains the default passwordless path. Cognito does
not combine an enrolled TOTP factor with `EMAIL_OTP`; users who opt into TOTP
must use the explicitly enabled password-plus-authenticator path. No customer
secrets are committed. The Cloudflare token and origin secret are operational
configuration only.

## Work and acceptance

- [x] Configure Cognito optional software-token MFA and password auth required by TOTP.
- [x] Add a secret-backed origin-header guard that is inactive until a configured SSM parameter exists.
- [x] Add a Free-plan Worker source and documented staged rollout.
- [x] Define versioned, private, SSE-S3 encrypted CloudTrail management-event storage with log-file validation.
- [x] Add focused guard tests and static Terraform contracts.
- [ ] Deploy the reviewed Terraform saved plan and complete the documented edge rollout.

## Validation

` .venv/bin/python -m pytest -q tests/test_serverless_runtime.py `: 31 passed.

## Follow-up

Deploy only after the plan is reviewed. Verify the Worker endpoint succeeds and
the direct API endpoint returns 403 before calling the edge guard active.
