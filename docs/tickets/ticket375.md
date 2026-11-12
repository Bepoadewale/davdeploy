# ticket375 — reconcile Nova source and hosted release status

PR: draft to be opened immediately after the bootstrap commit  
Branch: `docs/reconcile-nova-release-375`

## Problem / goal

Update current-state documentation after backend PRs #371–#374. Keep merged
source separate from deployed control-plane evidence, preserve all capability
scope and customer-facing claims, and state clearly that the new secret-read
deny is source only until a protected release includes it.

## Current repo state

- Backend main is at PR #374 merge commit `fa2213b`.
- Merged-main CI run `43162411486` passed all seven jobs.
- The deployed backend remains at PR #369's verified protected release; PR
  #374 did not run Terraform or change AWS resources.
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

## Acceptance criteria

- [ ] Current source commit and merged-main CI are exact.
- [ ] Deployed source and feature gates reflect verified release evidence.
- [ ] PR #374 is described as merged source, not deployed; no AWS mutation or
  customer workload is claimed.
- [ ] Full capability scope and existing product claims are preserved.
- [ ] Documentation conventions and diff checks pass.
- [ ] Final-head CI passes and review finds no blocker.

## Acceptance status

- [ ] Status reconciliation, local documentation checks, final review and CI
  complete.
- [ ] No deployment or customer workload is part of this documentation PR.

## Tests / validation performed

To be recorded after the status edits and checks.

## Evidence files produced

- `docs/tickets/ticket375.md`

## Boundaries

This is a documentation-only reconciliation. It does not enable the Nova plan
runner, change pricing or approval gates, deploy the backend, or alter any AWS
resource. The private Nova goal ledger remains outside this repository.

## Follow-up work

Continue with the next dependency-ready hosted plan/state, customer-role,
pricing, and exact-approval integration work. Do not claim hosted customer
planning or workload lifecycle until actual evidence exists.
