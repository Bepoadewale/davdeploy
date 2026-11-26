# ticket523 — Reconcile Nova execution handoff after ECS Express stack

PR: #523  
Branch: `docs/nova-handoff-523`

## Problem / goal

The active Nova goal handoff still identifies merged PR #518 as the next step
and uses a stale `main` baseline. The current implementation path is the open,
stacked ECS Express renderer, actual-plan policy, and pricing work in PRs #519,
#520, and #522. Keep the acceptance distinctions accurate and give the next
session a verified starting point without claiming the ECS Express runner or
Nova-originated execution is complete.

## Scope

- Update `COMPOSED_EXECUTION_GOAL.md` to identify current `main`, current draft
  PR dependencies, CI evidence, open gates, and the next dependency-ready work.
- Update `NOVA_CAPABILITY_EVIDENCE_MATRIX.md` to record the current ECS Express
  source status and retain the distinction between direct customer-side
  lifecycle evidence and Nova dispatch.
- Reconcile Terraform monitor and customer-side inventory status without
  changing AWS resources or the hosted control plane.

## Current repo state

- Backend `main` is `4cc177c2605c2ee313c161fe83b9eac02fc83aa0` after merged PR
  #521.
- PRs #519, #520, and #522 are open drafts. All have passing final-head CI,
  but no recorded reviews. PR #522 depends on #520.
- The direct ECS Express lifecycle evidence in PR #437 and private Batch
  evidence in PR #517 satisfy the general customer-side lifecycle gate for
  those exact tested shapes; neither proves Nova dispatch.
- The actual-plan policy, effective IAM review, complete cost review, and
  isolated ECS Express runner lifecycle remain open.

## Evidence checked

- Current backend `main`: `4cc177c2605c2ee313c161fe83b9eac02fc83aa0`, merged PR
  #521.
- PR #519 head `403ea5a331e7e29b611d4a2f04b7aeb9a7d111ed`, final-head run
  `45884741945`: seven checks passed.
- PR #520 head `3be5a9e59f919e19bf18233c5c4b65bcb57aafe4`, final-head run
  `45888420911`: seven checks passed.
- PR #522 head `38fd230b2f13211237b96a07d1dd26fee4d76fc1`, final-head run
  `45895348910`: seven checks passed.
- The three ECS Express PRs are open drafts with no recorded reviews. PRs #519
  and #520 are based on `dbbf7c1`; PR #522 is stacked on #520.
- The Terraform monitor reports 75 terminal records and no active operations;
  process inspection found no active Terraform plan, apply, or destroy.
- Read-only AWS checks verified the customer-side account and found seven
  DavDeploy Batch job definitions in inactive status. The tested Batch stacks
  are already absent. No AWS mutation was performed.
- The control plane was not inspected or changed for this documentation
  reconciliation. Previously recorded SageMaker lineage evidence remains
  protected.

## Research / references used

- [`COMPOSED_EXECUTION_GOAL.md`](../product/COMPOSED_EXECUTION_GOAL.md) —
  active acceptance gates and next-step handoff.
- [`NOVA_CAPABILITY_EVIDENCE_MATRIX.md`](../product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md)
  — capability-to-evidence status and limits.
- [PR #519](https://github.com/Bepoadewale/davdeploy/pull/519),
  [PR #520](https://github.com/Bepoadewale/davdeploy/pull/520), and
  [PR #522](https://github.com/Bepoadewale/davdeploy/pull/522) — current
  default-off ECS Express renderer, plan policy, and pricing stack.
- [`test437.md`](../test/test437.md) and [`test517.md`](../test/test517.md) —
  direct customer-side evidence for the exact ECS Express and Batch shapes.

## Work planned for the PR

1. Reconcile the active goal handoff with current backend `main` and the open
   ECS Express dependency stack.
2. Update the capability evidence matrix without conflating direct
   customer-side lifecycle with Nova dispatch.
3. Run the documentation checker and whitespace validation; require final-head
   GitHub checks before merging.

## Acceptance criteria

- [x] The handoff identifies the current `main` baseline and does not list the
  merged PR #518 documentation reconciliation as pending work.
- [x] The current open PR stack, heads, passing final-head CI runs, dependencies,
  and unresolved review/evidence gates are recorded.
- [x] Direct ECS Express and Batch evidence remains accepted for the exact
  customer-side shapes tested and is not represented as Nova dispatch.
- [x] Current Terraform monitor and Batch inventory status are stated without
  claiming the inactive job definitions were deleted.
- [x] The next action is actionable and does not enable the renderer, mutate
  AWS, or alter the hosted control plane.
- [x] Documentation conventions and `git diff --check` pass.
- [ ] Final-head GitHub Actions checks pass.

## Acceptance status

The handoff and matrix are reconciled to current `main` and the open PR state.
Documentation checks and final-head CI remain to be completed.

## Tests / validation performed

- `GITHUB_PR_NUMBER=523 python3 scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- Final-head GitHub Actions checks are pending.

## Boundaries

- Do not mutate the hosted control plane, runtime, state, or lock resources.
- Do not delete AWS resources, inactive Batch history, retained lineage
  evidence, local worktrees, or protected local files.
- Do not enable customer execution or claim a Nova-dispatched workload.
- Preserve uncommitted changes found in the PR #520 worktree and untracked
  provider-plan output files found in the PR #519 worktree; review them before
  any worktree synchronization.

## Validation plan

- Run the repository documentation-convention checker for PR #523.
- Run `git diff --check`.
- Require all final-head GitHub Actions checks to pass before merging.

## Evidence files produced

No `docs/test/test523.md` is required. This is a documentation-only
reconciliation and performs no customer workload test or cloud mutation.

## Follow-up work

Review PRs #519/#520/#522, validate their provider-generated actual-plan
contract, effective IAM permissions, full costs, and isolated customer-side
renderer lifecycle. Do not enable execution until those gates pass.
