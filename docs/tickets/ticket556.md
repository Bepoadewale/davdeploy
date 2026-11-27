# ticket556 — bind declared Lambda secret ARN to managed RDS secret

PR: [#556](https://github.com/Bepoadewale/davdeploy/pull/556) (draft)
Branch: `fix/nova-managed-secret-reference-556`

## Problem / goal

After PR #555 normalized resource IDs, a fresh hosted v18 run failed before CodeBuild with safe `credential_value` feedback at `resources[*]`. When the proposal explicitly declares one Lambda `*_SECRET_ARN` environment variable and exactly one RDS resource, safely replace a literal string value with a typed reference to that RDS resource's AWS-managed master secret. Never retain or expose the literal.

## Current repo state

- Backend main: `69d4274aa19ad9cfa8338f0025869163af67987b` (PR #555).
- Protected release plan `46039945706` and apply `46040738691` succeeded; migrations, six Lambda hashes, API health, and authenticated CLI `/api/v1/me` passed.
- Fresh hosted run `3b5b2a3e-96f8-4167-9af9-ea1c5ccdebb6` failed before CodeBuild with bounded `credential_value` feedback and no artifact. Raw proposal/values were not fetched. Do not retry it.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py` — permits RDS-managed master-secret outputs and typed references only in Lambda `*_SECRET_ARN` variables.
- `apps/api/src/davdeploy/nova_contract_generation.py` — deterministic transformations before strict schema validation.
- `docs/test/test555.md` — v18 ID failure and no-apply boundary.

## Work planned for the PR

1. Recognize only one RDS resource and one literal value in `environment[0].variables.<NAME>_SECRET_ARN` on a Lambda resource.
2. Ensure that RDS resource enables its AWS-managed master secret and declares the exact sensitive `master_user_secret[0].secret_arn` output.
3. Replace the literal with the existing typed `resource_reference` structure.
4. Leave multiple RDS resources, multiple secret inputs, other field names/locations, malformed shapes, and raw password arguments unchanged so strict validation rejects them.
5. Add direct tests for safe conversion, uniqueness, no raw-value retention, ambiguous fail-closed behavior, and end-to-end proposal validation.
6. After deployment, create a fresh undecided review and one plan-only generation run; inspect only safe diagnostics or a value-free artifact summary.

## Acceptance criteria

- [x] Only the single unambiguous Lambda secret ARN case is repaired.
- [x] Literal values are absent from the normalized output; the generated reference targets the uniquely declared RDS-managed secret output.
- [x] Multiple databases, multiple candidate variables, other variable names, and standalone raw password fields remain rejected. Supported RDS password fields are removed only when bound to the unique Lambda secret-ARN consumer.
- [x] Strict contract/reference validation, policy, and no-apply boundary remain unchanged.
- [x] Malformed non-string resource types remain available to strict validation and the bounded repair loop.
- [x] Focused tests, full `make verify`, and the required clean-room cycle pass and are recorded.
- [x] Documentation conventions and required PR CI pass.
- [ ] Fresh deployed plan-only run reaches a plan artifact or actionable bounded feedback without customer approval/apply.
- [ ] Full hosted gate is claimed only with supported API, private storage, DB behavior, async behavior, live pricing, and plan-policy evidence.

## Acceptance status

Implementation and local validation are complete. A review found and fixed a malformed-resource-type repair-path issue. Focused tests, full verification, and the prescribed clean-room cycle pass. Documentation conventions and required PR CI pass. Protected release and fresh hosted plan-only result remain pending.

## Tests / validation performed

- Authenticated read-only status query for the v18 run; only safe diagnostics were inspected.
- Prior-head focused tests: `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest -q tests/test_nova_managed_secret_normalization.py tests/test_terraform_generation.py` — 61 passed.
- Prior-head `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python` — 2,080 passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose checks passed. One existing Starlette deprecation warning.
- Final-head focused tests: `pytest -q tests/test_nova_managed_secret_normalization.py tests/test_terraform_generation.py` — 62 passed, including malformed resource-type bounded-repair regression.
- Final-head targeted Ruff, documentation convention check, and `git diff --check` passed.
- Final-head `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python` — 2,081 passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose checks passed. One existing Starlette deprecation warning.
- Required clean-room cycle passed at `0078bc90d41d2c9a20242e88a2d7d2f6f430f8b4` in detached worktree `/private/tmp/davdeploy-nova-556-cleanroom`, using isolated Compose project `davdeploy-nova-556-cleanroom`, tmpfs PostgreSQL, and external venv `/private/tmp/davdeploy-nova-556-venv`. Bootstrap, smoke, API contract, customer-plan E2E, seed, simple/complex/degraded/Day-2/failure/readiness-failure demos, trace check, and full verify passed. Final clean removed only the scoped Compose containers/network and generated `.local` and venv; absence checks passed. Worktree and Compose override remain.
- Required PR CI run `46043864593`: all seven checks passed at code head `0078bc90d41d2c9a20242e88a2d7d2f6f430f8b4`.
- Documentation conventions and diff checks passed.

## Evidence files produced

- `docs/tickets/ticket556.md`
- `docs/test/test556.md`

## Boundaries

Never accept or persist literal credentials. Do not weaken secret field filters or the typed-reference path restriction. Preserve the unapproved review and plan-only execution boundary. No workload approval, apply, or destroy. Preserve protected local files and audit evidence.

## Follow-up work

If the strict validation now reaches planning, inspect current regional pricing, exact saved-plan policy, and support for the requested composed resources. Do not call the plan customer-ready until every condition is evidenced.
