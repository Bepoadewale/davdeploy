# ticket395 — define typed health assertion contracts

PR: https://github.com/Bepoadewale/davdeploy/pull/395
Branch: `feat/typed-health-assertions-395`

## Problem / goal

Nova proposals currently record health assertions as an arbitrary string kind,
a target resource, and prose. Define a bounded, typed health assertion
contract that can later be consumed by deterministic probe handlers. Keep all
assertions explicitly proposed and unexecuted until a trusted executor records
real observations.

## Current repo state

Backend `main` is at PR #394 commit `650468c62d36abd869bcd563db9c5a6c326f07b8`.
PR #393 binds proposal verification requirements into the saved-plan manifest,
but the health assertion kind is still arbitrary and no Nova customer workload
has run health probes.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py`
- `apps/api/src/davdeploy/generated_plan_artifacts.py`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/product/NOVA_EXECUTION_ADR.md`

## Work planned for the PR

- Replace arbitrary health assertion kinds with explicit typed variants and
  per-kind bounded fields.
- Bind each assertion to compatible declared resource types and reject
  malformed, unsupported, or unsafe target/path/threshold payloads.
- Require event-processing checks to bind a declared SQS source and Lambda
  consumer through a typed event-source mapping.
- Keep Kubernetes workload readiness unavailable until the shared resource
  graph can represent and validate Kubernetes workloads.
- Preserve canonical manifest serialization and clearly unexecuted status.
- Add negative tests for invalid values, unknown fields and bounds.

## Acceptance criteria

- [x] Health assertion kinds are explicit, bounded and represented in the shared contract.
- [x] Inputs cannot encode arbitrary URLs/commands, unbounded waits or secret material.
- [x] The shared proposal contract advances to 1.1, generation prompt to v4, and manifest versions increment for the changed serialized contract.
- [x] Proposal evidence remains marked unvalidated and unexecuted.
- [x] Focused tests, `make verify`, and docs conventions pass.
- [ ] Required CI passes.
- [x] No cloud calls, probe execution, customer plan, or workload occurs in this PR.

## Acceptance status

- [x] Typed assertion catalog and bounded per-kind fields implemented; the runner still has no probe executor.
- [ ] Hosted pull-request CI, independent review and merge pending.

## Tests / validation performed

- Focused: `tests/test_generated_deployment_contract.py tests/test_generated_plan_artifacts.py tests/test_nova_plan_codebuild.py tests/test_nova_plan_runs.py tests/test_terraform_generation.py tests/test_customer_plan_review.py` — 191 passed.
- `make verify` — 1,086 passed; Ruff, OpenAPI snapshot, Actions configuration, and Docker Compose configuration checks passed. One existing Starlette/httpx deprecation warning remains.
- `.venv/bin/python scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Required CI — pending.

## Evidence files produced

- `docs/tickets/ticket395.md`
- `docs/test/test395.md`.

## Boundaries

This PR defines the proposal contract only. It does not claim to implement
runtime probes, certify workloads, or perform customer apply/teardown.

## Follow-up work

Implement trusted probe dispatch and real observation persistence after hosted
apply and lifecycle reconciliation are ready.
