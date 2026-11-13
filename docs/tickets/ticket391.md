# ticket391 — reconcile Nova plan-runner deployment evidence

PR: https://github.com/Bepoadewale/davdeploy/pull/391
Branch: `docs/reconcile-nova-plan-runner-deployment-391`

## Problem / goal

Update the durable status and PR #390 ticket with exact evidence from its
successful operations-bootstrap and protected control-plane deployments.

## Current repo state

Backend `main` is at `ae9ec4450d527141081e95707a1c3ee05126b683` (PR #390).
The protected control-plane apply `43389226372` completed successfully after
plan `43388286514`; exact deployment and read-only verification are recorded
in `docs/test/test391.md`.

## Research / references used

- PR #390 and its deployment runs `43388286514` / `43389226372`.
- `PROJECT_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`, and
  `docs/product/EXECUTION_READINESS_MATRIX.md`.
- Current read-only AWS checks and `https://api.davdeploy.tech/healthz`.

## Work planned for the PR

- Record verified source, plan/apply, account, migration, Lambda, policy and
  health evidence without implying customer workload readiness.
- Reconcile ticket #390's follow-up and acceptance status.

## Acceptance criteria

- [x] Exact hosted control-plane deployment and read-only verification are
  recorded in a PR-numbered evidence file.
- [x] Current status docs and ticket #390 agree on deployed version and gates.
- [x] No customer plan/apply, workload certification, pricing readiness or
  customer lifecycle capability is claimed without evidence.
- [x] Required local documentation checks pass.
- [ ] Hosted CI passes and the PR is merged.

## Acceptance status

- [x] Documentation and deployment evidence are reconciled.
- [x] Local documentation validation complete.
- [ ] Pull request CI and merge pending.

## Tests / validation performed

- `python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.

## Evidence files produced

- `docs/test/test391.md`
- `docs/tickets/ticket391.md`

## Boundaries

This documentation change does not start a customer plan, apply, or workload.

## Follow-up work

Continue with customer-role/effective-permission evidence, tenant-isolated
plan execution, trusted pricing, exact-plan approval and lifecycle
certification.
