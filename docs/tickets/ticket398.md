# ticket398 — reconcile Nova workspace artifact status

PR: https://github.com/Bepoadewale/davdeploy/pull/398
Branch: `docs/reconcile-nova-workspace-397`

## Problem / goal

The durable readiness documents stop at PR #393/#395 even though PR #397 has
merged the exact Terraform execution-workspace artifact. Reconcile source,
deployed release, evidence, and remaining apply/pricing/health gates without
claiming the new workspace artifact is deployed or used by an apply worker.

## Current repo state

Backend main is merge commit `12c39b4f495c034824f8ca00c7693a644015e9e3` after
PR #397. Merged-main CI run `43457148983` passed all seven jobs. Latest hosted
control-plane release remains PR #390. PR #397's final-head CI passed all
seven jobs; local and isolated clean-room evidence is in `docs/test/test397.md`.

## Research / references used

- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `PROJECT_STATUS.md`
- `CODEX_BACKLOG.md`
- `docs/tickets/ticket397.md` and `docs/test/test397.md`

## Work planned for the PR

- Reconcile current source and hosted release versions in the readiness,
  implementation, and project status documents.
- Record PR #397's separately encrypted, versioned workspace artifact and
  exact-object verification as merged source only.
- Preserve the existing cost, hosted plan, effective customer role, apply,
  observation, recovery, and teardown blockers.
- Record the next dependency-ready work without reopening or replacing pricing
  PR #318.

## Acceptance criteria

- [x] Current source through PR #397 is distinct from latest hosted PR #390.
- [x] PR #397 does not claim an apply worker, customer workload, or deployment.
- [x] Pricing PR #318 remains closed/held; its blocker is unchanged.
- [x] Health assertions remain proposed until deterministic probes execute and
  persist observed evidence.
- [x] Documentation conventions and diff checks pass locally.
- [ ] Required hosted PR checks pass.

## Acceptance status

- Documentation reconciled; final PR checks pending.

## Tests / validation performed

- `python3 scripts/check_doc_conventions.py` passed.
- `git diff --check` passed.
- Merged-main CI run `43457148983` passed all seven jobs.
- PR #398 required hosted checks pending.

## Evidence files produced

- `docs/tickets/ticket398.md`
- PR #397 evidence remains in `docs/test/test397.md`.

## Boundaries

This PR is documentation-only. It does not change runtime behavior, enable any
feature flag, deploy, alter customer-facing claims, or change pricing direction.

## Follow-up work

Continue independent hosted execution groundwork. Complete pricing only after
the account owner directs what to do with the closed PR #318 implementation.
Exact-plan apply, deterministic observations, recovery, and teardown remain
unproven.
