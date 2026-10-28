# ticket192 — Workspace support lifecycle and final evidence reconciliation

PR: [#192 — Workspace support ticket lifecycle](https://github.com/Bepoadewale/davdeploy/pull/192)
Branch: `feat/support-ticket-lifecycle`

## Problem / goal

Let workspace members see the status/history of their support requests, let workspace support
managers update those states, and correct final historical validation evidence.

## Current repo state

Support requests were durable but creation-only: customers could not retrieve their own request
history and workspace administrators/operators had no bounded status-management route.

## Research / references used

Existing tenant-scoped support-ticket model, current Settings workflow, and merged ticket #191.

## Work planned for the PR

Add tenant-scoped support-ticket listing/state updates, preserve role boundaries, and reconcile
the remaining merged-validation record.

## Acceptance criteria

- [x] Members see only their own workspace support requests unless they manage the workspace.
- [x] Operators/administrators can update bounded ticket states and actions are audited.
- [x] Historical evidence does not describe merged validation as pending.
- [ ] Full validation and CI pass.

## Acceptance status

Implementation complete locally; validation and CI are pending.

## Tests / validation performed

Recorded in `docs/test/test192.md`.

## Evidence files produced

- `docs/test/test192.md`

## Boundaries

No email is sent, no support ticket is exposed outside its workspace, and no cloud resource,
customer workload, credential or public webhook is changed.

## Follow-up work

Add externally authorised support ownership/escalation tooling only after a support operating model
is selected.
