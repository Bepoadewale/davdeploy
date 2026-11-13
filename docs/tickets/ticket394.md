# ticket394 — reconcile source and deployment status after PR #393

PR: https://github.com/Bepoadewale/davdeploy/pull/394
Branch: `docs/reconcile-plan-manifest-status-394`

## Problem / goal

Reconcile the current source and hosted-release status after PR #393. Make clear
that proposal health, recovery, cost assumptions and limitations are now bound
to the saved-plan manifest in source, but remain proposed/unvalidated and are
not evidence of pricing, probe execution, or a deployed customer workflow.

## Current repo state

Backend `main` is at `3db0d979c9eb0810b183244281789f139d28e19f` (PR #393).
Merged-main CI run `43399159484` passed all seven jobs. The latest hosted
control-plane release remains PR #390; PR #393 is source-only.

## Research / references used

- `docs/test/test391.md` and `docs/test/test393.md`
- `PROJECT_STATUS.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `CODEX_BACKLOG.md`

## Work planned for the PR

- Record exact current source commit and merged-main CI.
- Keep the last deployed backend release separate from current source.
- Update the readiness and backlog statements without claiming customer readiness.

## Acceptance criteria

- [x] Current source and merged-main CI identify PR #393 and its exact commit.
- [x] Latest hosted control-plane deployment remains identified separately as PR #390.
- [x] Product readiness and pricing/apply/health/lifecycle limitations remain accurate.
- [x] Documentation convention and diff checks pass; hosted CI is pending.
- [x] No customer plan or workload is executed by this documentation change.

## Acceptance status

- [x] Current source and latest deployed version are distinguished.
- [x] PR #393's unvalidated manifest evidence and remaining launch gates are recorded.
- [ ] Hosted CI and merge are complete.

## Tests / validation performed

- `scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Hosted CI and merge — pending.

## Evidence files produced

- `docs/tickets/ticket394.md`
- `docs/test/test394.md`

## Boundaries

This documentation change performs no AWS calls or customer workflow actions.

## Follow-up work

Continue the authenticated hosted Nova plan-only journey, pricing integration,
and health/recovery/teardown implementation under their existing gates.
