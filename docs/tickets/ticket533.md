# ticket533 — Read the DavDeploy CLI session through native macOS Keychain

PR: #533
Branch: `fix/cli-native-keychain-read-533`

## Problem / goal

The stored CLI session could not be resolved because the `security` command
timed out after 15 seconds on this macOS session. A native Swift `Security`
framework lookup returned the existing item immediately. Use the same native
Keychain API for reads that the CLI already uses for writes, without exposing
the stored session in terminal output.

## Current repo state

- PR #528 added Cognito password-plus-TOTP login and stores the verified
  session in macOS Keychain.
- `resolve_token` read the item through the `security` executable with a
  15-second timeout, while `_store_keychain_secret` already used Swift's
  `Security` framework.
- The current Nova control plane is deployed from main commit
  `f300676aa3af32a76136947c4f4870cee498b5e6`.

## Research / references used

- `apps/api/src/davdeploy/cli_auth.py` existing Keychain write implementation.
- Native `SecItemCopyMatching` read against the configured service/account;
  only item presence was printed during the manual check.
- `tests/test_cli_auth.py` session resolution and credential redaction tests.

## Work planned for the PR

- Read the session using Swift `Security` on macOS.
- Return a missing-item result separately from a generic read failure.
- Keep secret bytes inside the captured subprocess result and Python process;
  never print native error details or secret values.
- Preserve the `security` executable fallback when Swift is unavailable.

## Acceptance criteria

- [x] Existing Keychain sessions resolve through native macOS Keychain access.
- [x] Missing items remain distinguishable from Keychain failures.
- [x] Errors do not include secret values or native Keychain output.
- [x] Focused authentication tests and Ruff pass locally.
- [ ] Required hosted CI passes.

## Acceptance status

- [x] Native Keychain read is implemented and locally verified.
- [ ] Required hosted CI passes.
- [ ] CLI-only repository discovery and hosted plan retry are complete.

## Tests / validation performed

- `uv run --project . --extra dev pytest -q tests/test_cli_auth.py` — 11 passed.
- `uv run --project . --extra dev ruff check apps/api/src/davdeploy/cli_auth.py tests/test_cli_auth.py` — passed.
- `git diff --check` — passed.
- Using the stored session through `resolve_token` verified `/api/v1/me` as a
  workspace administrator and read the verified plan-only connection; no token
  or Keychain value was emitted.

## Evidence files produced

- `docs/test/test533.md`

## Boundaries

- No new Cognito login, password, or authenticator code was entered for this
  evidence; the pre-existing stored session was read.
- No AWS workload resources were created, changed, or deleted.
- This does not change authentication factors, tenant checks, or CLI token
  precedence.

## Follow-up work

Use the CLI's stored session for repository discovery, intent and architecture
review, and the hosted plan-only retry. Keep plan approval and apply disabled
until the exact plan, pricing, policy, and ownership evidence is sufficient.
