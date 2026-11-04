# ticket323 — Reconcile Nova implementation and launch boundaries

PR: https://github.com/Bepoadewale/davdeploy/pull/323
Branch: `docs/pr323-nova-readiness-status`

## Problem / goal

Refresh only the Nova readiness claims in `PROJECT_STATUS.md`,
`docs/IMPLEMENTATION_STATUS.md`, and `CODEX_BACKLOG.md` after PRs #320 and
#321 merged. Keep source changes, deployed state, and unproven launch gates
distinct.

## Current repo state

- Backend main is `f57bf4b` (PR #321).
- PR #320, “add bounded Nova proposal repair loop,” merged on 2026-11-04.
- PR #321, “deny unencrypted EBS volumes in Nova plans,” merged on 2026-11-04.
- No Nova-generated plan has been deployed.
- PR #318 is closed and awaits owner direction on the pricing-evidence path.
- The hosted plan-only runner, tenant-scoped remote state, and actual-cost gate
  remain incomplete. PR #322 is open, but its existence does not mean the gate
  is complete.

## Research / references used

- GitHub PR records for #318, #320, #321, and #322.
- Current `PROJECT_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`, and
  `CODEX_BACKLOG.md` on main.
- `AGENTS.md` and `scripts/check_doc_conventions.py`.

## Work planned for the PR

- Record merged source changes from #320 and #321 with clear limits on what
  they establish.
- State consistently that no Nova-generated plan has been deployed.
- Record that #318 is closed awaiting owner direction and that the hosted
  plan-only runner, tenant-scoped remote state, and actual-cost gate remain
  incomplete.
- Update only the three named status/backlog documents and this ticket.

## Acceptance criteria

- [ ] The three status/backlog documents distinguish merged source from
  deployed and validated product behavior.
- [ ] They record #320 and #321 as merged.
- [ ] They state that no Nova-generated plan has been deployed.
- [ ] They state that #318 remains closed pending owner direction and that the
  hosted plan-only runner, tenant-scoped remote state, and actual-cost gate are
  incomplete.
- [ ] No implementation code, AWS resource, or private local goal file is
  changed.
- [ ] Documentation convention and diff checks pass.

## Acceptance status

Implementation and validation pending.

## Tests / validation performed

Pending documentation convention and `git diff --check` validation. This is a
documentation-only change; no runtime test, Terraform command, or AWS call is
required or planned.

## Evidence files produced

No runtime evidence file is required because this PR is documentation-only and
performs no customer workload operation. `docs/test/test323.md` will not be
created.

## Boundaries

Documentation only. No implementation code, deployment, AWS resource, customer
data, PR #318, or private local goal file is changed.

## Follow-up work

Complete the hosted plan-only runner, tenant-scoped remote state, and actual-cost
gate before claiming that Nova-generated plans are ready for hosted execution.
