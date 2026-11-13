# ticket396: Reconcile Nova health-contract source status

PR: https://github.com/Bepoadewale/davdeploy/pull/396
Branch: `docs/reconcile-health-contract-status-396`

## Problem / goal

Record the merged PR #395 health-assertion contract in the backend readiness
documents without implying that probes execute or that hosted customer health
is observed.

## Current repo state

Backend `main` is at `5473e1de4bf5c6b8c73ea69dd58aa2e84c032e68` (PR #395).
The latest hosted control-plane release remains PR #390 commit
`ae9ec4450d527141081e95707a1c3ee05126b683`; PR #395 has not been deployed.

## Research / references used

- PR #395: <https://github.com/Bepoadewale/davdeploy/pull/395>
- Merged-main CI: <https://github.com/Bepoadewale/davdeploy/actions/runs/43422825929>
- `docs/test/test395.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `CODEX_BACKLOG.md`

## Work planned for the PR

- Record PR #395 and merged-main CI as source evidence.
- Keep the latest hosted control-plane release separately identified.
- State that typed health assertions are proposals only; runtime probes,
  observations, pricing, apply, recovery and teardown remain incomplete.
- Keep this PR documentation-only.

## Acceptance criteria

- [x] Record PR #395 and merged-main CI as source evidence.
- [x] Keep the latest hosted control-plane release separately identified.
- [x] State that typed health assertions are proposals only; runtime probes,
  observations, pricing, apply, recovery and teardown remain incomplete.
- [x] Keep the PR documentation-only; no runtime test evidence file is needed.

## Acceptance status

- [x] Documentation updates and local validation are complete; required CI is pending.

## Tests / validation performed

- `.venv/bin/python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Required GitHub PR checks — pending.

## Evidence files produced

- This ticket. A runtime test evidence file is not required because no
  executable behavior or customer workload changes.

## Boundaries

This PR records existing evidence only. It does not deploy source, call AWS or
Nova, execute probes, create a customer plan, apply infrastructure, or claim
customer readiness.

## Follow-up work

Implement a trusted observation path and continue the held pricing and hosted
plan/apply/lifecycle work under their existing gates.
