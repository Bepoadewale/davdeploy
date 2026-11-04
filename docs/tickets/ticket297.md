# ticket297 — Persist typed renderer outputs on module instances

PR: Pending draft creation
Branch: `feat/persist-typed-renderer-outputs`

## Problem / goal

PR #295 validates typed outputs and resolves declared references, but the hosted CodeBuild reconciliation path stores renderer outputs only on the run. A dependent module therefore cannot yet consume durable typed outputs from its exact dependency instance.

## Current repo state

- Main includes PR #296 (`9d14bd1`), which persists a unique CodeBuild build ID on a single module row and targets callbacks to that row.
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
- Add focused tests and update execution-status documentation.

## Acceptance criteria

- [ ] Raw Lambda/API outputs normalize to the declared `api_url` and `lambda_arn` ports.
- [ ] Unknown/missing/malformed raw output values fail closed before module outputs are persisted.
- [ ] A successful callback persists typed outputs only on its matched module instance.
- [ ] Legacy runs retain their existing run-level artifact behavior.
- [ ] Multi-module CodeBuild remains fail-closed.
- [ ] PR-numbered ticket/evidence and status documentation are accurate.
- [ ] Focused, full, clean-room and GitHub CI checks pass.

## Acceptance status

Pending implementation.

## Tests / validation performed

Pending implementation.

## Evidence files produced

No AWS workload evidence is expected. This PR validates local typed-output conversion and persistence only.

## Boundaries

No AWS resource mutation, hosted schema migration, renderer enablement, or composed customer deployment is included.

## Follow-up work

Wire persisted typed references into renderer input configuration and implement durable dependency-wave scheduling before enabling composed CodeBuild work.
