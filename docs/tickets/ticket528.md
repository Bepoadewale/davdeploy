# ticket528 — Add secure Cognito login to the DavDeploy CLI

PR: #528
Branch: `feat/cli-cognito-auth`

## Problem / goal

The CLI requires a manually provisioned bearer token and has no supported
Cognito login flow. Add a human sign-in command using password plus required
authenticator-app TOTP, verify the identity against DavDeploy, and store the
session securely so governed CLI requests can use it without printing tokens.

## Current repo state

- PR #528 starts from backend `main` at `a456b84aa17600daf2b2c0bfe51d3bddb67e59ba`.
- The CLI currently requires `--token` or `DAVDEPLOY_TOKEN` and has no login flow.
- Cognito uses `USER_PASSWORD_AUTH`, followed by `SOFTWARE_TOKEN_MFA`.
- Backend API authorization verifies a Cognito identity token. AWS operator
  credentials do not grant workspace authorization.
- This package changes only CLI authentication. It does not create AWS resources,
  modify hosted configuration, reset MFA, or broaden product permissions.

## Research / references used

- `apps/api/src/davdeploy/cli.py` is the installed `davdeploy` command.
- `apps/api/src/davdeploy/client.py` sends bearer-token requests to the governed API.
- `davdeploy-frontend/src/auth/cognitoEmail.ts` defines the product's Cognito
  password, software-token MFA, and refresh flows.
- The configured frontend user-pool client supports password and refresh auth;
  its refresh lifetime is one day.

## Work planned for the PR

- Add `davdeploy auth login` with hidden password and authenticator-code prompts.
- Verify the returned identity against `GET /api/v1/me` before persisting it.
- Store the session in macOS Keychain; never accept passwords/codes as command
  line arguments or print bearer tokens.
- Reuse and refresh a valid stored session for later CLI requests; preserve the
  explicit `--token` and `DAVDEPLOY_TOKEN` override behavior.
- Document setup and session expiry.

## Acceptance criteria

- [x] CLI login implements the Cognito password plus software-token challenge.
- [x] Workspace identity is verified by `GET /api/v1/me` before saving tokens.
- [x] Tokens are stored only in Keychain, are not shown in output, and refresh
      occurs before API calls when the ID token is near expiry.
- [x] Invalid/expired credentials fail with actionable text and no token or
      sensitive Cognito response in output.
- [x] Existing explicit bearer-token usage remains compatible.
- [ ] Focused tests, documentation conventions, required CI and review pass.

## Acceptance status

Implemented and locally verified. Required hosted CI and PR review are pending.
No live DavDeploy sign-in has been performed from this PR yet.

## Tests / validation performed

- `uv run --project . --extra dev pytest -q tests/test_cli_auth.py tests/test_agent_interfaces.py` — 17 passed.
- `GITHUB_PR_NUMBER=528 python3 scripts/check_doc_conventions.py` — passed.
- `uv run --project . --extra dev ruff check apps/api/src/davdeploy/cli.py apps/api/src/davdeploy/cli_auth.py tests/test_cli_auth.py` — passed.
- `git diff --check` — passed.
- `uv run --project . davdeploy --api-url https://api.davdeploy.tech auth login --help` — command registered and options displayed.

## Evidence files produced

- No customer workload evidence. A CLI authentication check alone is not a
  customer workload run.

## Boundaries

- Do not use AWS operator credentials as workspace identity.
- Do not change Cognito MFA policy or create/reset user accounts.
- Keep customer connection, plan, approval and workload evidence in the Nova
  acceptance PR that performs those operations.
- Cross-platform secure credential storage is outside this macOS Keychain
  implementation and must be reported clearly.

## Follow-up work

After a valid session is established, use the CLI/API path for the isolated
Nova test connection, plan-only role verification and first hosted plan.
