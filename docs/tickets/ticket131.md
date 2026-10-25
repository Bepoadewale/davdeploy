# ticket131: Wake the worker after cloud-execution confirmation

PR: #131
Branch: fix/cloud-execution-queue-wakeup

## Problem / goal

Close the event-driven handoff gap between final administrator confirmation and a durable `QUEUED` cloud-execution run.

## Current repo state

The worker intentionally has no polling heartbeat. A run is woken when created, while it is still awaiting confirmation. After confirmation it becomes queued without a second wake-up. No customer apply started from this gap.

## Research / references used

- The bounded SQS worker handler and its durable cloud-execution claim loop.
- The cloud-execution queue transition in `ProductService`.
- A real queued customer-pilot run that was safely consumed before it could be claimed.

## Work planned for the PR

- Send a minimal SQS wake-up after the post-confirmation durable commit.
- Add a regression test asserting the queue transition emits exactly one cloud-execution wake-up.

## Acceptance criteria

- [x] A ready run remains unable to execute before explicit confirmation.
- [x] Exact confirmation commits `QUEUED` and emits a non-sensitive wake-up.
- [x] Focused tests and lint pass locally.
- [ ] Required GitHub CI passes and the correction is deployed.
- [ ] The real queued pilot run is claimed after the correction is deployed.

## Acceptance status

Implementation and focused local validation are complete. CI, merge, deployment, and live-pilot confirmation remain.

## Tests / validation performed

- `.venv/bin/python -m pytest -q tests/test_cloud_execution.py` passed: 7 tests.
- `.venv/bin/python -m ruff check apps/api/src/davdeploy/service.py tests/test_cloud_execution.py` passed.
- `git diff --check` passed.

## Evidence files produced

- `docs/tickets/ticket131.md`
- Live customer-pilot evidence continues in `docs/test/test130.md`.

## Boundaries

The wake-up carries only event kind and durable run ID. Terraform commands, tenant data, plan material, and credentials remain in the database and trusted runner boundary.

## Follow-up work

- Merge and deploy this correction through the protected Terraform workflow.
- Continue the real customer-pilot proof in PR #130.
