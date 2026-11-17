# ticket423 — reconcile Nova source and hosted status after PR #422

PR: https://github.com/Bepoadewale/davdeploy/pull/423
Branch: `docs/reconcile-pr422-status`

## Problem / goal

Reconcile current Nova source and hosted deployment status after PR #422 merged. Keep the security-profile verification change clearly marked as source-only until it is deployed, and preserve the distinction between role-profile verification, effective permissions, hosted plans, and customer workload evidence.

## Current repo state

- Backend `main` is `8c84827ddbd32f5c937f83a393c177a825afbfb3` (PR #422).
- The hosted control plane remains deployed from PR #420 commit `9951caa9244128b1551fea3af66b1bdbf884c800`, plan `43981566184`, saved-plan apply `43982396577`; PR #422 has not been deployed.
- Draft PR #399 remains open. Apply and credential gates remain disabled; there is no hosted Nova customer plan or apply lifecycle evidence.
- Read-only AWS inventory in account `654654474502`, region `us-east-1`, found no SageMaker endpoint, model, or endpoint configuration; four tagged Batch definitions remain inactive. SageMaker lineage evidence remains retained.
- The Terraform run monitor is empty. Preserve the untracked `--only-show-errors` file and `.venv-pr399/`.

## Research / references used

- `PROJECT_STATUS.md`
- `CODEX_BACKLOG.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/customer-aws-connection.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket422.md`
- PR #422 merge commit and final-head CI run `44027382887`

## Work planned for the PR

- Update status snapshots to distinguish current backend `main` from the earlier hosted deployment.
- Record that PR #422 is merged but its role-profile verification is not deployed.
- Preserve the limits: profile checks are not full effective-permission attestation, and no hosted customer plan or workload is proven.
- Record retention of the isolated clean-room artifacts under the deletion-safety boundary; no cleanup or infrastructure mutation is performed.

## Acceptance criteria

- [x] Current source and hosted control-plane commits are distinguished in the status documents.
- [x] PR #422 is recorded as merged and not deployed, without implying a customer role or workload was verified.
- [x] PR #399 remains accurately documented as draft, gated, and without hosted customer apply/lifecycle proof.
- [x] AWS and local monitor evidence is stated without deleting or mutating resources.
- [x] Documentation conventions and `git diff --check` pass on the current PR content.
- [ ] Required PR checks pass on the final PR head.

## Acceptance status

The status reconciliation and local documentation checks are complete. Final
GitHub PR checks remain pending.

## Tests / validation performed

- PR #422 head `cfc8bb9` passed all seven checks in run `44027382887`.
- `make verify PY=.venv-pr399/bin/python` passed 1,281 tests; the focused six-file suite passed 152 tests.
- `GITHUB_PR_NUMBER=423 python3 scripts/check_doc_conventions.py` and
  `git diff --check` passed after the current documentation edits.
- Required PR #423 checks are pending after adding this ticket.

## Evidence files produced

- `docs/tickets/ticket423.md`
- Status-document changes in this PR; no customer workload test was performed, so no `docs/test/test423.md` is required.

## Boundaries

- Documentation only; do not deploy the control plane or change Nova feature gates.
- Do not run Terraform or mutate AWS resources.
- Do not issue customer credentials or claim a Nova customer workload was applied or certified.
- Preserve SageMaker lineage evidence, `--only-show-errors`, `.venv-pr399/`, and the retained clean-room artifacts.
- Do not delete files, Docker volumes, or other resources without explicit approval.

## Follow-up work

After an explicitly authorized protected control-plane release of PR #422, establish a real customer plan-only journey with a verified customer role. The complete hosted apply, health, recovery, destroy, and independent absence cycle remains unproven.
