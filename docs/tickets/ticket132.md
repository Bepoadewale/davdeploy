# ticket132: Persist generated cloud execution context

PR: #132
Branch: fix/persist-cloud-execution-context

## Problem / goal

Ensure a trusted worker receives the generated run ID and result artifact URI after a cloud-execution request is committed and later claimed.

## Current repo state

Cloud-execution context was stored in a JSON column. Mutating its nested environment in place after flush could leave the generated per-run values out of the durable record. The bounded runner correctly failed closed before CodeBuild or Terraform could start.

## Research / references used

- SQLAlchemy JSON dirty-tracking behavior for nested mutable values.
- The CodeBuild execution adapter's required environment contract.
- The real customer-pilot failure evidence, which contained no CodeBuild submission or workload resources.

## Work planned for the PR

- Replace, rather than mutate, the persisted execution-environment JSON value after the run ID is generated.
- Add a persistence regression test.

## Acceptance criteria

- [x] Generated run ID and result URI are part of a replaced JSON value before commit.
- [x] A fresh ORM read includes both generated values.
- [x] Focused tests and lint pass locally.
- [ ] Required GitHub CI passes.
- [ ] The correction is deployed before a new approved customer apply attempt.

## Acceptance status

Implementation and focused local validation are complete. CI, merge, deployment, and a new customer governed run remain.

## Tests / validation performed

- `.venv/bin/python -m pytest -q tests/test_cloud_execution.py` passed: 8 tests.
- `.venv/bin/python -m ruff check apps/api/src/davdeploy/service.py tests/test_cloud_execution.py` passed.
- `git diff --check` passed.

## Evidence files produced

- `docs/tickets/ticket132.md`
- Live customer-pilot evidence continues in `docs/test/test130.md`.

## Boundaries

This fixes durable metadata only. It does not weaken execution gates, run Terraform, or cause a CodeBuild submission by itself.

## Follow-up work

- Merge and deploy this correction through the protected Terraform workflow.
- Create a new approved execution run, then continue the real pilot in PR #130.
