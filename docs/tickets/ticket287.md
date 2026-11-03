# ticket287 — Correct terminal-state checks for module lifecycle evidence

PR: https://github.com/Bepoadewale/davdeploy/pull/287
Branch: `fix/lifecycle-evidence-terminal-states`

## Problem / goal

The composed execution helper accepts only generic `SUCCEEDED`, `HEALTHY`, or
`ABSENT` states for every lifecycle operation. It can therefore reject valid
persisted results such as `DESTROYED_VERIFIED` and `CLEANUP_VERIFIED`, or count
health evidence as plan completion. Define operation-specific terminal states
and test them.

## Current repo state

The universal execution contract computes dependency ordering and cleanup order.
Its terminal-evidence helper has fixture coverage for successful apply and
cleanup absence, but is not currently used by the hosted single-renderer worker.
Multi-module customer execution remains disabled.

## Research / references used

- `apps/api/src/davdeploy/universal_execution.py`
- `apps/api/src/davdeploy/service.py` hosted lifecycle state transitions
- `tests/test_universal_execution.py`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`

## Work planned for the PR

- Use operation-specific terminal-state sets for plan, apply, observe, rollback,
  destroy, and cleanup verification.
- Reject unsupported operation names and avoid treating failed or partial
  module records as complete.
- Add focused tests for each lifecycle terminal state and mixed outcomes.

## Acceptance criteria

- [x] Each operation recognizes only its appropriate terminal evidence.
- [x] A failed or incomplete module prevents graph completion.
- [x] Unknown operation names remain rejected.
- [ ] Required CI passes.

## Acceptance status

The implementation and full local verification pass. GitHub CI is pending.

## Tests / validation performed

`make verify` passed: 418 tests, Ruff, Actions configuration, OpenAPI snapshot,
and Docker Compose configuration checks. `python3 scripts/check_doc_conventions.py`
and `git diff --check` passed.

## Evidence files produced

No AWS workload evidence is expected. This PR changes only the internal
evidence-completeness contract.

## Boundaries

This does not enable additional renderers or change hosted execution gates.

## Follow-up work

Integrate graph-level per-module scheduling and dependency output binding into
the hosted worker, then validate composed workloads through AWS.
