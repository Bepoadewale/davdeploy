# ticket382 — reconcile the retained customer template and control-plane release

PR: [#382](https://github.com/Bepoadewale/davdeploy/pull/382) (draft)
Branch: `docs/reconcile-nova-network-template-release-382`

## Problem / goal

PR #381 preserved the previously published customer plan-role template while
publishing its replacement, and the resulting template plus PR #379 control-
plane source have now been deployed. Repository status still describes the
older release. Record exact source/deployment evidence without implying that a
customer role, hosted Nova plan, or workload was installed or executed.

## Current repo state

- Backend source and deployed source are PR #381 merge commit
  `a12205972cc124d08d85845f30c9b574f7cf87fd`.
- Merged-main CI run `43257709757` passed all seven required jobs.
- Template-host apply `pr381-template-host-a122059` completed successfully:
  1 object added, 0 changed, 0 destroyed.
- Protected control-plane plan `43260003885` and exact saved-plan apply
  `43261766144` deployed this source; GitHub deployment `7743511328`.
- Protected untracked `--only-show-errors` is not part of this change.

## Research / references used

- `docs/tickets/ticket381.md` and `docs/test/test381.md`
- `docs/test/test379.md` and current deployed Lambda environment/package checks
- `PROJECT_STATUS.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `CODEX_BACKLOG.md`

## Work planned for the PR

- Update #381's ticket and evidence to distinguish its pre-merge read-only
  checks from the verified post-merge publication and control-plane release.
- Reconcile current source/deployment sections and backlog status.
- Preserve the explicit gaps for customer role installation/effective
  permissions, hosted planning, pricing, exact-plan approval, apply, health,
  recovery, teardown, and composed certification.

## Acceptance criteria

- [x] The PR ticket and evidence file identify the exact merged source and
  deployed release.
- [x] Template publication and retention are verified without claiming a
  customer role or workload was created.
- [x] All repository status pages describe the runner, broker, plan reviews,
  state API, and hosted certification as disabled.
- [x] Pricing and exact cost-bound approval remain unavailable; customer
  apply/lifecycle and composed certification remain incomplete.
- [x] Documentation conventions and diff checks pass locally on this change.
- [x] Reconciliation head `5cd8d3b5b2f411013ed0cf6b278764b136546f7c` passed
  all seven required CI jobs in run `43265887734`; manual final-diff review
  found no blocker.
- [ ] PR is merged.

## Acceptance status

- [x] Source and hosted deployment evidence have been reconciled.
- [x] CI and review passed for the reconciliation head.
- [ ] Merge remains pending.

## Tests / validation performed

The release evidence is recorded in `docs/test/test382.md`.
`GITHUB_PR_NUMBER=382 .venv/bin/python scripts/check_doc_conventions.py` and
`git diff --check` passed locally. CI run `43265887734` passed all seven jobs
for commit `5cd8d3b5b2f411013ed0cf6b278764b136546f7c`; manual final-diff review
found no blocker.

## Evidence files produced

- `docs/test/test382.md`
- `docs/tickets/ticket381.md`
- `docs/test/test381.md`
- `PROJECT_STATUS.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `CODEX_BACKLOG.md`

## Boundaries

This is a documentation reconciliation for already completed operations. It
does not install a customer role, verify its effective permissions, enable
hosted Nova planning, create a customer plan, or apply customer infrastructure.
The private Nova strategy and status ledger stay outside the repository.

## Follow-up work

Continue the hosted plan-only worker, customer-role effective-permission
verification, tenant-isolated state access, trusted pricing, exact-plan
approval, and customer lifecycle implementation. Do not reopen or replace
pricing PR #318 without account-owner direction.
