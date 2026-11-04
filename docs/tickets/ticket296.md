# Ticket 296: Durable module build identity and exact reconciliation

## Goal

Persist the identity of the CodeBuild operation on the exact module instance it
executes, so callback reconciliation can progress from run-level records toward
safe per-module scheduling without applying one result to every graph node.

## Repository state

- Backend main includes PR #295 (`464dd0b`), which validates typed outputs and
  provides a reference resolver.
- The hosted worker still submits/reconciles one build per run and currently
  advances every module row together.
- The existing CodeBuild adapter rejects multi-module runs.

## Research and references

- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- PRs #289–#295 and `apps/api/src/davdeploy/service.py`

## Work

- Add a durable, unique CodeBuild identity to a module instance and migrate the
  database schema safely.
- Associate only the dispatched module with its build and completion result.
- Validate result identity against the run, module instance, operation, and
  immutable input digest before persisting outcomes.
- Preserve single-renderer behavior and fail closed for unsupported composed
  dispatch. This PR must not enable a new hosted renderer or workload.
- Update the execution goal and readiness matrix with exact status.

## Acceptance criteria

- [ ] Module build identity is durable and unique; legacy rows migrate safely.
- [ ] Reconciliation updates only the matching module instance.
- [ ] Duplicate, stale, mismatched, or ambiguous callback results cannot
  overwrite terminal module outcomes.
- [ ] Existing single-module behavior remains compatible.
- [ ] Multi-module work remains fail-closed until durable scheduling is complete.
- [ ] PR-numbered tests/evidence and status documentation are accurate.

## Validation

Pending implementation.

## Evidence

Pending implementation.

## Boundaries and follow-up

No AWS resources are created by this PR. This is an incremental persistence and
reconciliation foundation; it does not establish composed hosted execution,
safe retries, rollback, or customer launch readiness.
