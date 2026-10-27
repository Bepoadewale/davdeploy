# test185 — Hosted Cognito email-OTP acceptance

Date: 2026-10-27
Execution type: controlled hosted identity, API, CLI, and MCP acceptance
Customer repository: none
Commit: pending PR merge
AWS account: configured DavDeploy control-plane account
AWS region: us-east-1

## Resources created

One controlled Cognito identity and its personal workspace. No cloud connection, customer workload, or execution resource was created.

## Commands executed

- Confirmed a controlled Cognito sign-up using the delivered confirmation code.
- Initiated and completed Cognito `USER_AUTH` with the `EMAIL_OTP` challenge.
- Called hosted `POST /api/v1/onboarding` and authenticated `GET /api/v1/me` with the resulting ID token.
- Ran `davdeploy get-audit-events` against the hosted API using that ID token.
- Called the MCP `get_audit_events` tool against the hosted API using that same ID token.
- Reviewed the custom sender Lambda logs for a successful bounded invocation without logging a code.

## Observed result

Confirmation and sign-in codes were delivered through the custom sender. The confirmed identity successfully created a personal workspace; hosted `/api/v1/me`, the CLI, and the MCP request all returned successfully. No token, code, email address, or workspace identifier is retained here.

## Teardown

No infrastructure or workload was created. The controlled identity and workspace are retained for the browser acceptance journey.

## Final boundary

This proves the hosted identity and agent-client path. It does not prove a human browser click-through; that remains the final controlled acceptance step.
