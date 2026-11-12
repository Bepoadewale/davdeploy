# ticket375 — reconcile Nova source and hosted release status

PR: [#375](https://github.com/Bepoadewale/davdeploy/pull/375) (draft)
Branch: `docs/reconcile-nova-release-375`

## Problem / goal

Update current-state documentation after backend PRs #371–#374. Keep merged
source separate from deployed control-plane evidence, preserve all capability
scope and customer-facing claims, and state clearly that the new secret-read
deny is source only until a protected release includes it.

## Current repo state

- Backend main is at PR #374 merge commit `fa2213b`.
- Merged-main CI run `43162411486` passed all seven jobs.
- The deployed backend remains at PR #369's verified protected release,
  backend source `0481696d8a9aa1c73d789b2076a23f9c07ccc1fb`; PR #374 did not
  run Terraform or change AWS resources.
- Nova hosted customer planning remains disabled and has no customer workload
  evidence.

## Research / references used

- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `PROJECT_STATUS.md`
- `CODEX_BACKLOG.md`
- PR #374 source, ticket and test evidence.

## Work planned for the PR

- Reconcile backend source commit and merged-main CI in current status sections.
- Record PR #374 as merged source but not deployed; preserve the managed-policy
  review boundary and the fact runtime secret reads remain unavailable.
- Preserve the last verified deployed package, all disabled Nova gates, and
  outstanding pricing, customer planning, apply, operation and teardown gates.
- Reconcile the current-source sections in the product matrix, implementation
  status, project status, and backlog without rewriting dated historical rows.

## Acceptance criteria

- [x] Current source commit and merged-main CI are exact.
- [x] Deployed source and feature gates reflect verified release evidence.
- [x] PR #374 is described as merged source, not deployed; no AWS mutation or
  customer workload is claimed.
- [x] Full capability scope and existing product claims are preserved.
- [x] Documentation conventions and diff checks pass.
- [x] Manual final-diff review found no blocker.
- [ ] Final-head CI passes all required jobs.
- [x] No deployment or customer workload is part of this documentation PR.

## Acceptance status

- [x] Status reconciliation is complete and local documentation checks pass;
  manual review found no blocker and final-head CI is pending.
- [x] No deployment or customer workload is part of this documentation PR.

## Tests / validation performed

No runtime tests were required. `python scripts/check_doc_conventions.py` and
`git diff --check` passed. Manual final-diff review found no blocker. No AWS or
customer workload activity was performed.

## Evidence files produced

- `docs/tickets/ticket375.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `PROJECT_STATUS.md`

## Boundaries

This is a documentation-only reconciliation. It does not enable the Nova plan
runner, change pricing or approval gates, deploy the backend, or alter any AWS
resource. The private Nova goal ledger remains outside this repository.

## Follow-up work

Continue with the next dependency-ready hosted plan/state, customer-role,
pricing, and exact-approval integration work. Do not claim hosted customer
planning or workload lifecycle until actual evidence exists.
