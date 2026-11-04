# ticket323 — Reconcile Nova implementation and launch boundaries

PR: https://github.com/Bepoadewale/davdeploy/pull/323
Branch: `docs/pr323-nova-readiness-status`

## Problem / goal

Refresh only Nova readiness claims in `PROJECT_STATUS.md`,
`docs/IMPLEMENTATION_STATUS.md`, and `CODEX_BACKLOG.md` after PRs #320–#322
merged. Keep source changes, deployed state, and unproven launch gates distinct.

## Current repo state

- Backend main is `6c599e6` (PR #322).
- PR #320, “add bounded Nova proposal repair loop,” merged on 2026-11-04.
- PR #321, “deny unencrypted EBS volumes in Nova plans,” merged on 2026-11-04.
- PR #322 merged on 2026-11-04. Generated-plan manifests record pricing as
  unavailable, and approval is blocked until complete region-bound cost
  evidence exists. No trusted pricing evaluator is integrated yet.
- No Nova-generated plan has been deployed.
- PR #318 is closed; its pricing approach remains unresolved.
- The hosted plan-only runner and tenant-scoped remote state remain incomplete.
  PR #322 implements a fail-closed cost-availability approval gate, but no
  trusted pricing evaluator is integrated and generated plans cannot currently
  be approved.

## Research / references used

- GitHub PR records and merged implementation for #318, #320, #321, and #322.
- `docs/tickets/ticket322.md` and `docs/test/test322.md` on current main.
- Current `PROJECT_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`, and
  `CODEX_BACKLOG.md` on main.
- `AGENTS.md` and `scripts/check_doc_conventions.py`.

## Work planned for the PR

- Record merged source changes from #320 and #321, plus the #322 cost-availability
  gate, with clear limits on what they establish.
- State consistently that no Nova-generated plan has been deployed.
- Record that #318 is closed with its pricing approach unresolved and that the
  hosted plan-only runner, tenant-scoped remote state, and trusted pricing
  evaluator remain incomplete.
- Update only the three named status/backlog documents and this ticket.

## Acceptance criteria

- [x] The three status/backlog documents distinguish merged source from
  deployed and validated product behavior.
- [x] They record #320, #321, and #322 as merged.
- [x] They state that no Nova-generated plan has been deployed.
- [x] They state that #318 is closed with its pricing approach unresolved,
  that the #322 gate blocks approval until regional pricing is available, and
  that the hosted plan-only runner, tenant-scoped remote state, and trusted
  pricing evaluator remain incomplete.
- [x] No implementation code, AWS resource, or private local goal file is
  changed.
- [x] Documentation convention and diff checks pass.

## Acceptance status

Documentation updates are complete. Local documentation convention and diff
checks passed. All seven required GitHub Actions checks passed on the current
PR head `1f1aecdb4ce943f3917409dd9425f3ffecdb1239` in run
[41914451860](https://github.com/Bepoadewale/davdeploy/actions/runs/41914451860).

## Tests / validation performed

`GITHUB_PR_NUMBER=323 python3 scripts/check_doc_conventions.py` passed.
`git diff --check` passed. This is a documentation-only change; no runtime
test, Terraform command, or AWS call is required or planned.
All seven required CI checks passed on the current PR head
`1f1aecdb4ce943f3917409dd9425f3ffecdb1239` in run
[41914451860](https://github.com/Bepoadewale/davdeploy/actions/runs/41914451860):
cloud-contracts, docs-conventions, local-e2e, policy, python, secrets, and
supply-chain. The current PR head includes the merged PR #322 status update;
all required checks are complete.

## Evidence files produced

No runtime evidence file is required because this PR is documentation-only and
performs no customer workload operation. `docs/test/test323.md` will not be
created.

## Boundaries

Documentation only. No implementation code, deployment, AWS resource, customer
data, PR #318, or private local goal file is changed.

## Follow-up work

Integrate a trusted regional pricing evaluator and complete the hosted plan-only
runner and tenant-scoped remote state before generated plans can be approved or
used for hosted execution.
