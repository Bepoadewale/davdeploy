# ticket523 — Reconcile Nova execution handoff after ECS Express stack

PR: #523  
Branch: `docs/nova-handoff-523`

## Problem / goal

The active Nova goal handoff still identifies merged PR #518 as the next step
and uses a stale `main` baseline. The current implementation path is the
default-off ECS Express renderer and runner in PR #519, merged actual-plan
policy in PR #520, and pricing work in PR #522. Keep the acceptance
distinctions accurate and give the next session a verified starting point
without claiming the ECS Express runner or Nova-originated execution is
complete.

## Scope

- Update `COMPOSED_EXECUTION_GOAL.md` to identify current `main`, current draft
  PR dependencies, CI evidence, open gates, and the next dependency-ready work.
- Update `NOVA_CAPABILITY_EVIDENCE_MATRIX.md` to record the current ECS Express
  source status and retain the distinction between direct customer-side
  lifecycle evidence and Nova dispatch.
- Reconcile Terraform monitor and customer-side inventory status without
  changing AWS resources or the hosted control plane.

## Current repo state

- Backend `main` is `a456b84aa17600daf2b2c0bfe51d3bddb67e59ba` (merged PR #522).
- PR #520 (`c9ece16291af2c6a659e47ca0bad2867b2fd16c3`) merged; all seven
  final-head and merged-main checks passed in run `45899643291`.
- PR #519 remains an open draft at `00697d7b6b84ed7d0ff0fef7effb7cf0037392e7`;
  its seven checks passed in run `45903656967`.
- PR #522 (`a04c5909075bfe975ba1628aeef9851a7b317784`) merged after all seven
  checks passed in run `45900573713`.
- PR #524 remains an open draft correcting the merged #522 ticket's pricing
  evidence wording. Its diff is now two documentation files against `main`;
  head `75841d3ac80e8020b1b616fef07055167a8381c6` passed all seven checks in
  run `45907870966`.
- PR #525 remains an open draft stacked on #519. It pre-provisions
  connection-scoped ECS Express roles in a customer-side CloudFormation
  template and verifies their trust, tags, and policy attachments before
  runner operations. Final-head `bf876fe155a7fe946a457b6d61d74c25696893e0`
  passed all seven checks in run `45907548159`. This does not prove the
  runner's effective permissions or enable the renderer.
- PR #526 is an open draft security review. Final-head CI run `45910551656`
  passed all seven checks; source review confirmed the runner assumes its
  customer role without a session policy and that the `administrator-pilot`
  role can carry `AdministratorAccess`.
- PR #527 is an open draft stacked on #526. It documents AWS action/resource
  mapping and the computed-subnet scope gap for the ECS Express root. Its
  content head `4ac9ab04` passed all seven checks in run `45911833917`, and
  ticket-status head `36fa7031` passed all seven checks in run `45912427843`.
  It contains no policy code or cloud execution.
- The direct ECS Express lifecycle evidence in PR #437 and private Batch
  evidence in PR #517 satisfy the general customer-side lifecycle gate for
  those exact tested shapes; neither proves Nova dispatch.
- The actual-plan policy is merged and has been exercised with a provider-
  generated saved plan; effective IAM review and the isolated ECS Express
  runner lifecycle remain open. PR #525's role bootstrap and preflight
  verifier are source-only, and the customer execution-role policy still
  requires independent review.

## Evidence checked

- Current backend `main`: `a456b84aa17600daf2b2c0bfe51d3bddb67e59ba`.
- PR #519 head `00697d7b6b84ed7d0ff0fef7effb7cf0037392e7`, final-head run
  `45903656967`: seven checks passed.
- PR #520 head `c9ece16291af2c6a659e47ca0bad2867b2fd16c3`, run
  `45899643291`: all seven final-head and merged-main checks passed; merged.
- PR #522 head `a04c5909075bfe975ba1628aeef9851a7b317784`, run
  `45900573713`: all seven checks passed and it merged.
- PRs #519, #524, and #525 remain drafts; PRs #520 and #522 are merged.
- PR #524 head `75841d3ac80e8020b1b616fef07055167a8381c6` passed all seven
  checks in run `45907870966`. Its merge-base correction leaves only
  `ticket522.md` and `ticket524.md` changed against current `main`.
- PR #525 head `bf876fe155a7fe946a457b6d61d74c25696893e0` passed all seven
  checks in run `45907548159`; it is source-only and keeps the renderer
  disabled.
- PR #526 head `df82c553fcfeef388592b9b1a5ddeb0c787f1cae` passed all seven
  checks in run `45910551656`; it records the unbounded execution-role path.
- PR #527 head `4ac9ab04` records a sourced AWS permission map and the need to
  separate network foundation from ECS service creation. All seven checks
  passed on head `4ac9ab04` in run `45911833917` and on ticket-status head
  `36fa7031` in run `45912427843`. No AWS mutation or Terraform operation
  occurred.
- A provider-generated saved plan from the PR #519 root was evaluated under
  #520 policy. It yielded three review findings and no policy denials; this is
  plan-policy evidence only, not remote-state runner or lifecycle evidence.
- A live Price List evaluation of the saved plan returned 12 modeled lines
  and USD 1.27–415.81/month under synthetic usage assumptions. Its context
  digest was synthetic and no customer budget was supplied; it is not
  approval-bound customer pricing evidence.
- The Terraform monitor reports 75 terminal records and no active operations;
  process inspection found no active Terraform plan, apply, or destroy.
- Read-only AWS checks verified the customer-side account and found seven
  DavDeploy Batch job definitions in inactive status. The tested Batch stacks
  are already absent. One SageMaker test lineage action/context and its
  artifact association remain as retained evidence; no lineage records were
  deleted. No AWS mutation was performed.
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
- [x] The current open PRs, merged #520/#522 heads, passing final-head CI,
  and unresolved review/evidence gates are recorded.
- [x] Direct ECS Express and Batch evidence remains accepted for the exact
  customer-side shapes tested and is not represented as Nova dispatch.
- [x] Current Terraform monitor and Batch inventory status are stated without
  claiming the inactive job definitions were deleted.
- [x] PR #525's connection-scoped role bootstrap is classified as
  source-only, and effective runner-role permissions remain an open gate.
- [x] PRs #526 and #527 are classified as source reviews only; the broad role
  permission and computed-subnet policy gaps remain hard apply blockers.
- [x] The next action is actionable and does not enable the renderer, mutate
  AWS, or alter the hosted control plane.
- [x] Documentation conventions and `git diff --check` pass.
- [x] Final-head GitHub Actions run `45908603081` passed all seven checks for
  handoff commit `667de8be`; this status-record update receives a fresh run.

## Acceptance status

The handoff and matrix are reconciled to current `main`, merged PRs #520/#522,
and open drafts #519/#524/#525/#526/#527. All recorded PR #527 heads and
this handoff update passed final-head CI; a status-only follow-up records the
current run.

## Tests / validation performed

- `GITHUB_PR_NUMBER=523 python3 scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- Final-head run `45908603081` on `667de8be`: all seven checks passed.
- Follow-up ticket-status commit `5b6fd18d` passed all seven checks in run
  `45909113939`.
- Handoff head `9bddba795ea62eff0a7c07e7774057c1486a4f42` passed all seven
  final-head checks in run `45912889818`.

## Boundaries

- Do not mutate the hosted control plane, runtime, state, or lock resources.
- Do not delete AWS resources, inactive Batch history, retained lineage
  evidence, local worktrees, or protected local files. The prior request to
  approve cleanup did not identify a target set; no cleanup scope is authorized
  by this ticket.
- Do not enable customer execution or claim a Nova-dispatched workload.
- Preserve untracked provider-plan output files found in the PR #519 worktree;
  do not publish their contents.

## Validation plan

- Run the repository documentation-convention checker for PR #523.
- Run `git diff --check`.
- Require all final-head GitHub Actions checks to pass before merging.

## Evidence files produced

No `docs/test/test523.md` is required. This is a documentation-only
reconciliation and performs no customer workload test or cloud mutation.

## Follow-up work

Continue review of the #519/#524–#527 dependency stack, implement separate
phase identities and tested exact-plan permissions, then complete
approval-bound pricing and the authorized isolated remote-state renderer
lifecycle. The actual-plan policy in #520 is merged and has been evaluated
against a provider-generated plan. Keep the renderer disabled until the
remaining gates pass.
