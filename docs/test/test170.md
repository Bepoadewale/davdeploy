# test170 — Resend invitation adapter

Date: 2026-10-26

Execution type: local automated validation

Customer repository: not used

Commit: `f6ad6ef` plus documentation correction pending

AWS account: not contacted

AWS region: not contacted

## Resources created

None.

## Commands executed

```text
uv run pytest tests/test_invitation_email.py
uv run pytest
```

## Observed result

Passed. The focused adapter tests and the full backend suite pass: 291 tests passed.

## Teardown

No resources were created.

## Final boundary

Local tests only. No live Resend account, Cloudflare route, AWS sender, invitation, customer
workspace, or production runtime configuration was changed by this test run.

## Known limitations

This does not prove delivery until the Resend domain is verified and the hosted runtime receives a
sending-only API key.
