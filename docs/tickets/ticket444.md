# ticket444 — refresh Nova execution evidence after PR #443

PR: https://github.com/Bepoadewale/davdeploy/pull/444
Branch: `docs/nova-goal-after-443`

## Problem / goal

The canonical Nova handoff, capability matrix, and implementation status still
describe main through PR #441 and the apply-role proof as S3-only. Refresh the
current source, accepted customer-side ECS evidence, apply-role permission
matrix, AWS inventory, and Terraform monitor without changing the hosted
control plane or shrinking the 26-architecture-entry / 30-root scope.

## Current repo state

- Backend `main` is `e63d3ecbcc715d5a509e3f6b99382154a4bdc0d5` (PR #443).
- PR #443 adds an allow-policy size fix and records a direct same-account
  customer-role permission matrix for S3, SQS, and DynamoDB. All seven checks
  passed in run `45065309558` on head `2d15f39`.
- The latest hosted backend release remains PR #420, applied by run
  `43982396577` after plan `43981566184`; no control-plane access or mutation
  is part of this reconciliation.
- Direct ECS Express lifecycle evidence in PR #437 is accepted for the
  general goal's customer-side plan/apply/health/update/recovery/teardown gate.
  It was not Nova-generated or dispatched.
- AWS account `654654474502` in `us-east-1` has no tested DavDeploy SageMaker
  endpoint, model, or endpoint configuration. Four tagged Batch definitions
  are inactive. The SageMaker lineage action/context remain as audit evidence.
  Temporary PR #443 roles, stack, bucket, queue, and table are absent.
- The Terraform monitor has 16 terminal records and no active run. Preserve
  `--only-show-errors` and `.venv-pr399/`.

## Research / references used

- `docs/product/COMPOSED_EXECUTION_GOAL.md` — canonical execution handoff.
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` — 26/30 acceptance map.
- `docs/IMPLEMENTATION_STATUS.md` and `PROJECT_STATUS.md` — current product
  status summaries.
- `docs/tickets/ticket443.md` and `docs/test/test443.md` — role policy fix and
  isolated AWS evidence.
- Current GitHub PR #443 state, AWS inventory in account `654654474502`, and
  `scripts/terraform_run_monitor.py status`.

## Work planned for the PR

1. Refresh source and hosted-release snapshots through PR #443.
2. Record the direct ECS acceptance as the general customer-side gate and the
   S3/SQS/DynamoDB role matrix with its limits and provenance.
3. Reconcile the AWS inventory and run monitor without deleting retained
   lineage evidence or touching the control plane.
4. Keep all 26 architecture entries, 30 roots, cost and Nova-dispatch gaps.
5. Name the next dependency-ready SQS policy/lifecycle package.

## Acceptance criteria

- [x] Main, PR #443 and CI run `45065309558` are accurately recorded.
- [x] PR #437 is counted for the general customer-side lifecycle gate with
      direct-Terraform provenance.
- [x] PR #443's role evidence includes exact-plan permissions and cleanup,
      without claiming Nova credential issuance or cross-account trust.
- [x] AWS inventory and monitor match read-only current-state checks.
- [x] The 26/30 crosswalk and remaining Nova-specific execution gaps remain.
- [x] Documentation conventions, matrix row counts, and diff checks pass.
- [x] All seven required checks passed on documentation head `6ae6621` in run
      `45066910994`; the final ticket/evidence follow-up is also checked by PR
      CI before merge.
- [x] No control-plane, Terraform-state, or execution-gate mutation occurs.

## Acceptance status

The documentation refresh and local checks are complete. All seven required
checks passed on head `6ae6621` in run `45066910994`; the ticket/evidence
follow-up will receive its own required check run before merge.

## Tests / validation performed

Documentation-only. No new AWS workload or Terraform operation is part of this
PR. The existing direct evidence is in `docs/test/test437.md` and
`docs/test/test443.md`.

## Evidence files produced

- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `PROJECT_STATUS.md`
- `docs/tickets/ticket444.md`
- `docs/test/test444.md`

## Boundaries

Do not change the hosted control plane, Terraform state/locks, Nova execution
gates, customer credentials, or retained SageMaker lineage records. Preserve
the protected untracked backend file `--only-show-errors` and `.venv-pr399/`.
Do not claim that a Nova customer workload has been applied or certified.

## Follow-up work

Proceed with the next dependency-ready SQS queue policy and lifecycle package,
then continue the remaining role, dispatch, pricing, policy, and per-entry
acceptance work against all 26 architecture entries and 30 Terraform roots.
