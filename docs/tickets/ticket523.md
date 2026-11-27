# ticket523 — Reconcile Nova execution handoff after ECS Express stack

PR: #523  
Branch: `docs/nova-handoff-523`

## Problem / goal

The Nova handoff and capability matrix lagged new hosted planning evidence
and changes in the ECS Express feature stack. Reconcile them to current
source, PR status, verified cloud inventory, and acceptance gates without
claiming hosted workload execution or changing AWS resources.

## Scope

- Update `COMPOSED_EXECUTION_GOAL.md` to identify current `main`, current draft
  PR dependencies, CI evidence, open gates, and the next dependency-ready work.
- Update `NOVA_CAPABILITY_EVIDENCE_MATRIX.md` to record the current ECS Express
  source status and retain the distinction between direct customer-side
  lifecycle evidence and Nova dispatch.
- Reconcile Terraform monitor and customer-side inventory status without
  changing AWS resources or the hosted control plane.

## Current repo state

- Backend `main` is `f300676aa3af32a76136947c4f4870cee498b5e6` (PR #532).
- PR #531 records an authenticated hosted Nova plan attempt that omitted
  explicit file-storage, relational-data, and queue requirements. It failed
  before any saved-plan artifact existed; no workload apply or lifecycle
  evidence was produced.
- PR #532 fixes explicit allow-listed requirement retention in source. It has
  not been deployed to the hosted runtime and the plan attempt has not been
  rerun.
- PR #519 remains an open draft at
  `8a56669a76192e0ec8217b7abf8967f564c90cb8`. Latest final-head CI run
  `45928624349` passed all seven checks. Its renderer remains disabled pending
  effective permission proof and an isolated project-scoped remote-state
  lifecycle.
- PRs #525, #526, and #527 were merged into the #519 feature branch, not
  `main`. Their service-role bootstrap, security review, and AWS action map do
  not establish least-privilege runner permissions.
- PR #529 closed unmerged after its base branch was deleted. Its compact ECS
  policy is design-only; composite ECS actions still need exact action/resource
  and condition mapping before a safe implementation.
- PR #524 remains an open draft correcting the pricing evidence wording. Its
  current head is `75841d3ac80e8020b1b616fef07055167a8381c6`; prior-head run
  `45907870966` passed all seven checks. Recheck final-head CI before merge.
- The direct ECS Express lifecycle evidence in PR #437 and private Batch
  evidence in PR #517 satisfy the general customer-side lifecycle gate for
  those exact tested shapes; neither proves Nova dispatch.
- The actual-plan policy is merged and has been exercised with a provider-
  generated saved plan; effective IAM review and the isolated ECS Express
  runner lifecycle remain open. PR #525's role bootstrap and preflight
  verifier are source-only, and the customer execution-role policy still
  requires independent review.

## Evidence checked

- Current backend `main`: `f300676aa3af32a76136947c4f4870cee498b5e6`.
- PR #519 prior head `00697d7b6b84ed7d0ff0fef7effb7cf0037392e7`, run
  `45903656967`: seven checks passed; current head and run are recorded below.
- PR #520 head `c9ece16291af2c6a659e47ca0bad2867b2fd16c3`, run
  `45899643291`: all seven final-head and merged-main checks passed; merged.
- PR #522 head `a04c5909075bfe975ba1628aeef9851a7b317784`, run
  `45900573713`: all seven checks passed and it merged.
- PR #519 is an open draft; latest head `8a56669a76192e0ec8217b7abf8967f564c90cb8`
  passed all seven checks in run `45928624349`.
- PRs #525/#526/#527 are merged only into the #519 branch, not `main`. PR #529
  closed unmerged; PR #524 remains an open draft.
- PR #524 head `75841d3ac80e8020b1b616fef07055167a8381c6` passed all seven
  checks in run `45907870966`. Its merge-base correction leaves only
  `ticket522.md` and `ticket524.md` changed against current `main`.
- PR #525/#526/#527 were merged into the #519 branch, not `main`; all source
  remains disabled and no AWS mutation was performed.
- A provider-generated saved plan from the PR #519 root was evaluated under
  #520 policy. It yielded three review findings and no policy denials; this is
  plan-policy evidence only, not remote-state runner or lifecycle evidence.
- A live Price List evaluation of the saved plan returned 12 modeled lines
  and USD 1.27–415.81/month under synthetic usage assumptions. Its context
  digest was synthetic and no customer budget was supplied; it is not
  approval-bound customer pricing evidence.
- The Terraform monitor reports 75 terminal records and no active operations;
  process inspection found no active Terraform plan, apply, or destroy.
- Read-only AWS checks verified account `654654474502` and found seven
  DavDeploy Batch job definitions in inactive status. No SageMaker endpoints,
  models, or endpoint configurations were present. Tested Batch stacks are
  absent. SageMaker lineage action/context and related artifact associations
  remain as audit evidence; no AWS mutation was performed. The phrase
  “Approve this exact cleanup” did not identify which Batch definitions or
  lineage records to delete, so no cleanup was performed.
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
- [x] Current `main`, the #519/#524 status, the #525/#526/#527 feature-stack
  position, and unresolved runner/lifecycle evidence gates are recorded.
- [x] Direct ECS Express and Batch evidence remains accepted for the exact
  customer-side shapes tested and is not represented as Nova dispatch.
- [x] Current Terraform monitor and Batch inventory status are stated without
  claiming the inactive job definitions were deleted.
- [x] PR #531's hosted plan failure and PR #532's undeployed source fix are
  recorded without claiming a saved plan or workload lifecycle.
- [x] PR #525/#526/#527 are classified as feature-branch source changes that
  do not establish effective least-privilege runner permissions.
- [x] The next action is actionable and does not enable the renderer, mutate
  AWS, or alter the hosted control plane.
- [x] Documentation conventions and `git diff --check` pass.
- [ ] Final-head GitHub Actions checks pass for the updated PR #523 head.

## Acceptance status

The handoff and matrix are reconciled to current `main`, hosted planning
evidence, the #519 feature stack, and current read-only AWS inventory. Local
documentation validation is pending; PR #523 final-head CI must pass before
merge.

## Tests / validation performed

- `GITHUB_PR_NUMBER=523 python3 scripts/check_doc_conventions.py`: pending.
- `git diff --check`: pending after final edits.
- Final-head run `45908603081` on `667de8be`: all seven checks passed.
- Follow-up ticket-status commit `5b6fd18d` passed all seven checks in run
  `45909113939`.
- Handoff head `9bddba795ea62eff0a7c07e7774057c1486a4f42` passed all seven
  final-head checks in run `45912889818`.
- PR #519 current head `8a56669a76192e0ec8217b7abf8967f564c90cb8` passed all
  seven checks in run `45928624349`; this does not satisfy its open security
  and isolated lifecycle acceptance gates.

## Boundaries

- Do not mutate the hosted control plane, runtime, state, or lock resources.
- Do not delete AWS resources, inactive Batch history, retained lineage
  evidence, local worktrees, or protected local files. Cleanup approval is
  pending exact resource scope; no AWS deletion is part of this PR.
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

Continue the #519 dependency stack. Resolve exact ECS action/resource mapping
and least-privilege phase credentials, make customer pricing approval-bound,
and complete an authorized project-scoped remote-state lifecycle before
enabling the renderer. Separately deploy PR #532 through the protected
control-plane workflow and rerun the hosted Nova plan; do not infer workload
execution from the previous failed planning attempt.
