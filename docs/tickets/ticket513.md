# ticket513 — reconcile Nova status after PR #512

PR: https://github.com/Bepoadewale/davdeploy/pull/513 (draft)
Branch: `docs/nova-pr512-status-513`

## Problem / goal

PR #512 merged source-only Batch Fargate public IPv4 pricing, but the Nova goal
handoff, capability matrix, implementation status, project status, backlog,
and ticket #512 still describe it as draft or leave its final status incomplete. Reconcile the
records with the verified GitHub merge and CI evidence. Do not imply that this
source change was deployed or that any Nova customer workload was executed.

## Current repo state

- Backend `main` is `ef94983898cad92c8bd884725baec3c1cb072caf` (PR #512).
- PR #512 final-head CI passed all seven checks in run
  `45680499414`; merged-main CI passed all seven checks in run
  `45681334818`.
- PR #512 changed pricing source, tests, API contract, and goal evidence only.
  It did not mutate AWS, Terraform state/locks, or the hosted control plane.
- The AI infrastructure platform goal remains queued behind the active Nova
  goal.

## Research / references used

- GitHub PR #512 merge record and its final-head CI run `45680499414`.
- Merged-main CI run `45681334818` for commit
  `ef94983898cad92c8bd884725baec3c1cb072caf`.
- `docs/tickets/ticket512.md`,
  `docs/product/COMPOSED_EXECUTION_GOAL.md`,
  `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`, and
  `docs/IMPLEMENTATION_STATUS.md`, `PROJECT_STATUS.md`, and `CODEX_BACKLOG.md`.

## Work planned for the PR

1. Update source baseline and package state to merged PR #512 in the status
   docs, backlog, and goal handoff.
2. Record exact final-head and merged-main CI evidence.
3. Mark ticket #512 merged and accurately describe its separate public IPv4
   address-duration and maximum-attempt assumptions.
4. Update backlog and handoff to keep approval blocked for all unpriced network
   paths and material dependencies.
5. Preserve explicit separation between source evidence, hosted deployment,
   direct customer-side workload evidence, and Nova dispatch.

## Acceptance criteria

- [x] Every current status document names PR #512 as merged at `ef94983` and
  cites final-head and merged-main CI evidence.
- [x] Ticket #512 records merged status while retaining its tested limits and
  the lack of customer workload evidence.
- [x] No document implies that PR #512 was deployed, enables Batch approval,
  or proves Nova-dispatched customer execution.
- [ ] Documentation conventions, full required local verification, and all
  seven final-head CI checks pass.
- [x] No AWS, Terraform state/locks, hosted control-plane resources, or local
  protected files are changed.

## Acceptance status

- [x] Documentation reconciliation complete.
- [x] Local validation and documentation conventions pass.
- [ ] Final-head CI passed.
- [ ] PR reviewed and merged.

## Tests / validation performed

`make VENV=/Users/adewale/Projects/davdeploy/.venv verify` — 1,944 passed;
Ruff, Actions configuration, OpenAPI snapshot, and Docker Compose checks passed.
One upstream Starlette deprecation warning was emitted. `GITHUB_PR_NUMBER=513
python3 scripts/check_doc_conventions.py` and `git diff --check` passed. No
customer workload test was performed.

## Evidence files produced

No `docs/test/test513.md` is expected because no customer workload is run.

## Boundaries

Documentation-only. Do not apply or destroy Terraform, mutate AWS, access or
change the hosted control plane, delete any resource, alter the protected
untracked backend file `--only-show-errors` or `.venv-pr399/`, or claim Nova
customer workload certification.

## Follow-up work

Continue the active Nova goal with the next dependency-ready source or evidence
package. Keep all remaining unsupported pricing, hosted plan-only acceptance,
customer authorization, and Nova-dispatch gaps explicit.
