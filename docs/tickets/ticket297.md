# ticket297 — Persist typed renderer outputs on module instances

PR: https://github.com/Bepoadewale/davdeploy/pull/297
Branch: `feat/persist-typed-renderer-outputs`

## Problem / goal

PR #295 validates typed outputs and resolves declared references, but the hosted CodeBuild reconciliation path stores renderer outputs only on the run. A dependent module therefore cannot yet consume durable typed outputs from its exact dependency instance.

## Current repo state

- Main includes PR #296 (`9d14bd1`), which persists a unique CodeBuild build ID on a single module row and targets callbacks to that row. CI run [41760912071](https://github.com/Bepoadewale/davdeploy/actions/runs/41760912071) passed all seven jobs.
- The Lambda/API Terraform root emits `api_endpoint` and `lambda_arn`, while the typed contract exposes `api_url` and `lambda_arn`.
- The worker does not yet schedule dependency waves; multi-module CodeBuild remains fail-closed.

## Research / references used

- `apps/api/src/davdeploy/module_ports.py`
- `apps/api/src/davdeploy/service.py` CodeBuild result reconciliation
- `infrastructure/terraform/customer-workload-serverless-api/main.tf`
- PRs #294–#296 and `docs/product/COMPOSED_EXECUTION_GOAL.md`

## Work planned for the PR

- Define an explicit checked-in mapping from raw renderer output names/shapes to typed module output ports.
- Validate and persist typed outputs on the exact module instance associated with a successful CodeBuild result.
- Preserve legacy run-level output shape for compatibility and never persist secret contents.
- Make the dispatcher accept the exact typed work shape emitted by the Python adapter while rejecting unresolved dependencies and inline values.
- Add focused tests and update execution-status documentation.

## Acceptance criteria

- [x] Raw Lambda/API outputs normalize to the declared `api_url` and `lambda_arn` ports.
- [x] Unknown/missing/malformed raw output values fail closed before module outputs are persisted.
- [x] A successful callback persists typed outputs only on its matched module instance.
- [x] Sensitive Terraform outputs and rejected artifacts are not persisted.
- [x] Legacy runs retain their existing run-level artifact behavior.
- [x] Multi-module CodeBuild remains fail-closed.
- [x] The dispatcher accepts the adapter's `instance_id` and `input_bindings` fields but still rejects unresolved bindings and arbitrary fields.
- [x] PR-numbered ticket and status documentation are accurate.
- [x] Full isolated clean-room cycle passes on the final implementation commit.
- [ ] GitHub CI passes.

## Acceptance status

Implemented locally. Only the checked-in Lambda/API renderer has a raw-output
mapping. Successful CodeBuild reconciliation validates those values and stores
them on the callback's exact module instance. Sensitive, unknown, or malformed
outputs fail the run and are omitted from persisted artifacts. The CodeBuild
dispatcher accepts the typed instance/reference fields emitted by the adapter
while still rejecting unresolved dependencies and inline values. Multi-module
execution remains disabled.

## Tests / validation performed

Focused dispatcher and execution tests passed (56 passed, one existing
Starlette deprecation warning). Full `make verify` passed (479 tests passed; one
existing warning). The isolated clean-room cycle passed on final implementation
commit `d2ca805`; see `docs/test/test297.md`. Ruff, the PR documentation
convention check, OpenAPI snapshot, Compose configuration, and `git diff --check`
passed. GitHub CI is pending.

## Evidence files produced

No AWS workload evidence is expected. This PR validates local typed-output conversion and persistence only.

## Boundaries

No AWS resource mutation, hosted schema migration, renderer enablement, or composed customer deployment is included.

## Follow-up work

Wire persisted typed references into renderer input configuration and implement durable dependency-wave scheduling before enabling composed CodeBuild work.
