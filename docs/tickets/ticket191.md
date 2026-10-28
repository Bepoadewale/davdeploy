# ticket191 — Reconcile current readiness and provider boundaries

PR: pending
Branch: `chore/reconcile-readiness-contracts`

## Problem / goal

Bring current-status documentation and the active roadmap into line with the merged, deployed
control plane without overstating customer-cloud execution or public GitHub webhook capability.

## Current repo state

The hosted GitHub OIDC Terraform route has been dispatched successfully, and recent PRs have
merged and deployed. Several current-status and backlog lines still describe those states as
pending or describe already-replaced hosted fixtures as active gaps.

## Research / references used

Merged PR records, successful GitHub Actions plan/apply runs, current implementation status, and
the customer-beta boundary.

## Work planned for the PR

Reconcile current status/backlog documents; add fixture contracts for future observed-output,
pricing, and signed-webhook evolution without enabling a live provider or public callback.

## Acceptance criteria

- [ ] Current status no longer says the dispatched GitHub OIDC route is unexecuted.
- [ ] Completed hosted identity/persistence work is removed from active backlog items.
- [ ] Future pricing, observed-output, and webhook fixtures remain explicitly non-production.
- [ ] Documentation and automated tests pass.

## Acceptance status

Draft; implementation has not started.

## Tests / validation performed

Will be recorded in `docs/test/test191.md`.

## Evidence files produced

- `docs/test/test191.md`

## Boundaries

No customer workload, public webhook, cloud execution permission, queue message, or provider
integration is enabled or changed.

## Follow-up work

Record a controlled human browser journey and run an explicitly approved recovery drill.
