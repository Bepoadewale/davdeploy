# ticket303 — Allow the typed DynamoDB-to-Lambda input in the executor

PR: #303 (draft)
Branch: `fix/dispatcher-dynamodb-input`

## Problem / goal

The deployed fixed dispatcher still accepts only `uploads_bucket_name`, even though PR #302 added the approved `table_name` binding to the API renderer. Add a precise allowlist entry for the DynamoDB table name and verify its declared source output. Keep the hosted execution gates disabled.

## Current repo state

PR #301 added the gated DynamoDB renderer. PR #302 added table-scoped Lambda IAM and the API runner's deterministic table-name validation. The control-plane package was deployed by apply run `41781326222` with 0 additions, 6 in-place changes and 0 removals; database migration and `/healthz` checks succeeded. Post-deployment code review found the executor script rejects `table_name` before calling the API renderer. The renderer routes are still disabled for ordinary customer execution, so no workload is exposed.

## Research / references used

- `scripts/customer-workload-dispatcher.sh`
- `apps/api/src/davdeploy/module_ports.py`
- `apps/api/src/davdeploy/cloud_execution.py`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/test/test302.md`

## Work planned for the PR

- Allow only `uploads_bucket_name` and `table_name` in resolved Lambda renderer inputs.
- Require the corresponding input/output port pair: S3 bucket name from `bucket_name`, DynamoDB table name from `table_name`.
- Keep non-API modules unable to receive resolved inputs and keep arbitrary names/values rejected.
- Add dispatcher tests for DynamoDB binding success, mismatched binding, and extra fields.
- Update the readiness handoff to note PR #302 merged, its hosted deployment, and this narrow follow-up.

## Acceptance criteria

- [x] Correct S3 and DynamoDB typed references reach only the selected Lambda renderer.
- [x] Unknown keys, incorrect output names and unresolved/mismatched references fail before runner invocation.
- [x] DynamoDB and Lambda certification gates remain disabled by default.
- [ ] Focused tests, full verification, documentation conventions, clean-room cycle, and CI pass.
- [ ] Hosted execution remains gated; no AWS customer workload is created by this PR.

## Acceptance status

Bootstrap only; implementation and validation pending.

## Tests / validation performed

Focused dispatcher tests: 11 passed; `make verify` passed (507 tests; OpenAPI and Compose checks passed, with one existing Starlette/httpx deprecation warning). Ruff, shell syntax, documentation conventions, and diff checks passed. Clean-room cycle and PR CI are pending.

## Evidence files produced

- `docs/test/test303.md` (local contract proof; no AWS workload planned).

## Boundaries

This change closes an input-validation mismatch. It does not certify a real Lambda function using DynamoDB, enable customer execution, or prove the hosted callback/recovery lifecycle.

## Follow-up work

Run controlled composed AWS certification through the authorized customer execution workflow after the required renderer gates and source/plan evidence are configured.
