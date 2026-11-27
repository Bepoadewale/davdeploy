# ticket554 — actionable safe Nova graph validation feedback

PR: [#554](https://github.com/Bepoadewale/davdeploy/pull/554) (draft)
Branch: `fix/nova-graph-feedback-554`

## Problem / goal

Hosted run `e2395afb-6017-4ceb-9be1-6fdd5661e3c5` exhausted its v17 repair attempt with a generic root-level `value_error` and failed before CodeBuild. Known proposal graph, health, event, and cost validation causes should produce fixed, allowlisted guidance without exposing proposal content or exception text.

## Current repo state

- Backend main: `38849b326cb3ac6db5a8d96aad4cbcfce66a6fc2` (PR #553).
- The run is terminally `FAILED`, has no artifact, and has one safe root `value_error` diagnostic. No saved plan or workload was created.
- The architecture still lacks confirmed supported API + private storage + database + async composition and current regional price evidence.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py` — deterministic contract validators.
- `apps/api/src/davdeploy/terraform_generation.py` — bounded safe feedback and trusted prompt.
- `docs/test/test553.md` — prior hosted failure evidence and security boundary.

## Work planned for the PR

1. Map every known proposal graph validator cause to a fixed category and correction.
2. Keep unknown causes opaque and never return arbitrary exception text or model values.
3. Add sanitizer/prompt regression tests and bump the prompt version for the guidance change.
4. After deployment, run one fresh unauthenticated-approval plan-only generation and record its safe outcome.

## Acceptance criteria

- [x] Known proposal graph, reference, health, event binding, and cost-target errors have fixed categories/guidance.
- [x] Unknown validator errors retain fixed generic guidance without reflecting exception text.
- [x] Focused tests, Ruff, and diff checks pass.
- [x] Full `make verify` (2,064 tests plus Ruff, Actions configuration, OpenAPI, and Compose), documentation conventions, and local diff checks pass.
- [ ] Required PR CI passes.
- [ ] A fresh deployed plan-only run reaches a plan artifact or produces actionable bounded diagnostics.
- [ ] Any plan artifact proves supported API, private storage, database, async processing, current regional prices, and exact policy before being called acceptance evidence.

## Acceptance status

Implementation and full local validation are complete. Required hosted CI and the later fresh hosted plan-only proof remain pending.

## Tests / validation performed

- Authenticated read-only query of run `e2395afb-6017-4ceb-9be1-6fdd5661e3c5`: terminal failure, no artifact, v17 root-level safe `value_error`; no raw proposal was retrieved.
- `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest -q tests/test_terraform_generation.py tests/test_generated_deployment_contract.py` — 108 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python` — 2,064 passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose checks passed. One pre-existing Starlette deprecation warning.
- `GITHUB_PR_NUMBER=554 .../python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Required PR CI and deployed hosted plan-only run remain pending.

## Evidence files produced

- `docs/tickets/ticket554.md`
- `docs/test/test554.md`

## Boundaries

No customer workload approval, apply, or destroy. Never retrieve or emit raw proposal text, sensitive plan/state values, credentials, or signed URLs. Preserve protected local files and audit evidence. Keep fixture prices and unsupported architecture status explicit.

## Follow-up work

A fresh generated plan is only a first-stage artifact. The goal still requires exact policy approval, hosted apply, real application behavior, update/recovery, destroy, independent absence checks, and full finite-matrix/browser/CLI/MCP evidence.
