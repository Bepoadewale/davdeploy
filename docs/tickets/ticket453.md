# ticket453 — reconcile merged EventBridge evidence

PR: https://github.com/Bepoadewale/davdeploy/pull/453
Branch: `docs/reconcile-eventbridge-evidence-453`

## Current repo state

- Backend `main` is `6a193161aead202c4fda25b31cf70c512315961f` (PR #452).
- The direct AWS test prefix and local Terraform state are absent; the run
  monitor has no active operation.
- PR #452 policy changes are merged in source but are not deployed to the
  hosted control plane.

## Research / references used

- [`ticket452.md`](ticket452.md) — implementation scope, policy behavior,
  source limitations, and acceptance cases.
- [`test452.md`](../test/test452.md) — observed same-account delivery, failure,
  recovery, and cleanup evidence.

## Problem / goal

PR #452 merged after its direct EventBridge-to-SQS failure, dead-letter queue,
recovery, and cleanup test passed. The capability matrix, goal summary, and
ticket/test records still described #452 as a draft on the pre-merge baseline.
Reconcile those records to the verified merge commit and final CI run.

## Work planned for the PR

1. Update the capability matrix to the verified main commit and mark the
   EventBridge retry/DLQ plan checks as merged source, still undeployed.
2. Record PR #452's merge commit and final seven-check CI run in the goal,
   ticket, and direct-service evidence file.
3. Keep direct AWS test evidence separate from Nova dispatch and hosted
   execution claims.

## Evidence used

- [`test452.md`](../test/test452.md) — direct AWS run, monitored teardown,
  exact-prefix absence, and final PR CI evidence.
- PR #452 merged as `6a193161aead202c4fda25b31cf70c512315961f`; final head
  `9bfc02d70a89931a4037cb4c12a306bc7154d91f` passed all seven checks in run
  [45217552598](https://github.com/Bepoadewale/davdeploy/actions/runs/45217552598).
- The Terraform run monitor has 31 terminal records and no active operation.

## Acceptance criteria

- [x] The capability matrix and composed-goal status identify the merged
      backend commit and accurately distinguish source-only policy from direct
      AWS service evidence.
- [x] The test and ticket records identify PR #452's merge and final CI run.
- [x] Documentation conventions and `git diff --check` pass.
- [x] No AWS or hosted control-plane resource is changed by this follow-up.

## Acceptance status

The records are reconciled to the merged PR #452 commit and its final passing
CI run. The direct test prefix is absent and the Terraform monitor is idle.
No hosted control-plane or AWS resource was changed by this documentation PR.

## Tests / validation performed

- `python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.

## Evidence files produced

- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/test/test452.md`
- `docs/tickets/ticket452.md`
- `docs/tickets/ticket453.md`

## Boundaries

This PR only reconciles repository evidence. It does not deploy changes to the
hosted control plane, run Terraform, or change AWS resources. Preserve the
protected untracked `--only-show-errors` file and `.venv-pr399/`.

## Follow-up work

The broader capability, policy, pricing, and Nova-originated execution gaps
remain in [`NOVA_CAPABILITY_EVIDENCE_MATRIX.md`](../product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md).
This reconciliation does not close any of those gates.

## Scope boundary

This documentation reconciliation neither deploys the policy to the hosted
control plane nor claims Nova dispatch or general customer certification.
