# ticket530 — Review and approve generated plan artifacts from the CLI

PR: #530
Branch: `feat/cli-generated-plan-approval-530`

## Problem / goal

The CLI can authenticate and approve legacy architecture plans, but it has no
commands to inspect the safe summary for a generated Terraform plan artifact or
approve that exact artifact by its immutable manifest digest. Add both governed
API commands without exposing saved-plan bytes or bypassing backend checks.

## Scope

- Add `get-generated-plan-artifact --artifact-id` using the safe artifact review
  endpoint.
- Add `approve-generated-plan --artifact-id --manifest-sha256` using the
  generated-artifact approval endpoint.
- Document that approval is separate from apply and that the server validates
  the full evidence manifest.

## Acceptance criteria

- [x] CLI sends artifact reads to the tenant-scoped safe review endpoint.
- [x] CLI approval sends the exact caller-supplied manifest digest to the
  authenticated approval endpoint.
- [x] No saved-plan bytes, state data, credentials or MFA values are accepted
  or emitted by these commands.
- [x] Focused tests, lint and documentation checks pass locally.
- [ ] Required hosted CI passes.

## Current repo state

- CLI authentication is merged in PR #528.
- The hosted plan artifact approval endpoint already requires administrator
  authorization and an exact manifest digest; no artifact has yet passed the
  current Nova generation path for this workspace.

## Research / references used

- `apps/api/src/davdeploy/cli.py` and the shared authenticated API client.
- `GET /api/v1/generated-plan-artifacts/{artifact_id}` returns safe review
  evidence without plan bytes.
- `POST /api/v1/generated-plan-artifacts/{artifact_id}/approve` delegates
  final integrity and policy checks to the backend.
- `tests/test_generated_plan_review.py` covers server-side approval gates.

## Work planned for the PR

- Add CLI inspection and exact-manifest approval commands.
- Document the review-before-approval flow and the separate apply boundary.
- Add focused CLI routing tests and runtime evidence.

## Acceptance status

- [x] Safe artifact review command added.
- [x] Exact-manifest approval command added.
- [x] Focused tests and lint pass locally.
- [ ] Required hosted CI passes.

## Tests / validation performed

- `uv run --project . pytest -q tests/test_cli_generated_plan_approval.py tests/test_cli_auth.py` — 10 passed.
- `uv run --project . ruff check apps/api/src/davdeploy/cli.py tests/test_cli_generated_plan_approval.py` — passed.
- `uv run --project . python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Hosted CI pending.

## Evidence files produced

`docs/test/test530.md` records the local command-routing checks. Hosted approval
is not claimed because no generated plan artifact is ready for review.

## Boundaries

- This CLI command cannot bypass server-side workspace role, policy, pricing,
  manifest integrity or execution-readiness checks.
- Approval does not apply infrastructure.
- Saved-plan bytes and state are never fetched by the CLI review command.

## Follow-up work

Continue diagnosing the hosted Nova proposal-generation failure and produce a
validated saved-plan artifact before attempting human approval or apply.
