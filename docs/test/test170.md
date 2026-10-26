# test170 — Resend invitation adapter

## Commands executed

```text
uv run pytest tests/test_invitation_email.py
uv run pytest
```

## Result

Passed. The focused adapter tests and the full backend suite pass: 291 tests passed.

## Execution boundary

Local tests only. No live Resend account, Cloudflare route, AWS sender, invitation, customer
workspace, or production runtime configuration was changed by this test run.

## Known limitations

This does not prove delivery until the Resend domain is verified and the hosted runtime receives a
sending-only API key.
