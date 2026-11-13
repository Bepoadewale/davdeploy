# ticket395 — define typed health assertion contracts

PR: Pending creation
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
- Reject malformed, unsupported, or unsafe target/path/threshold payloads.
- Preserve canonical manifest serialization and clearly unexecuted status.
- Add negative tests for invalid values, unknown fields and bounds.

## Acceptance criteria

- [ ] Health assertion kinds are explicit, bounded and represented in the shared contract.
- [ ] Inputs cannot encode arbitrary URLs/commands, unbounded waits or secret material.
- [ ] Existing proposal and manifest digests remain canonical and tests are updated.
- [ ] Proposal evidence remains marked unvalidated and unexecuted.
- [ ] Focused tests, `make verify`, docs conventions, and required CI pass.
- [ ] No cloud calls, probe execution, customer plan, or workload occurs in this PR.

## Acceptance status

- [ ] Implementation and validation pending.

## Tests / validation performed

- Pending.

## Evidence files produced

- `docs/tickets/ticket395.md`
- `docs/test/test395.md` (to be added).

## Boundaries

This PR defines the proposal contract only. It does not claim to implement
runtime probes, certify workloads, or perform customer apply/teardown.

## Follow-up work

Implement trusted probe dispatch and real observation persistence after hosted
apply and lifecycle reconciliation are ready.
