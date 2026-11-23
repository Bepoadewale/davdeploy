# ticket464

PR: [#464 — docs: reconcile Nova evidence through PR 463](https://github.com/Bepoadewale/davdeploy/pull/464) (draft)

Branch: `docs/reconcile-kms-463-464`

## Problem / goal

PR #463 merged source-only KMS key plan checks and module defaults. The active
Nova backlog, composed-goal handoff, and capability evidence matrix still name
PR #461 as current backend `main`. Reconcile those snapshots and keep AWS
lifecycle and hosted Nova execution claims scoped to evidence actually
recorded.

## Current repo state

- Backend `main` is `f33ff461f85cb457fb4a6ed03b358a5a0615a180` (PR #463).
- PR #463 passed all seven required checks in CI run 45266750554.
- PR #463 adds source-only KMS checks for symmetric encryption, `ENCRYPT_DECRYPT`,
  automatic rotation, single-Region scope, and a 30-day deletion window.
- No customer-managed KMS key was created. The module's key policy, consumer
  binding, and customer-side lifecycle evidence remain open.
- The hosted control plane remains at its prior release and was not accessed
  or changed.
- The Terraform run monitor has 41 terminal records and no active runs.
- Preserve `--only-show-errors`, `.venv-pr399/`,
  `docs/test/fixtures/nova-batch-retry-458/terraform.tfstate`, and the
  untracked KMS module lock file created during local validation.

## Research / references used

- [PR #463](https://github.com/Bepoadewale/davdeploy/pull/463), merged at
  `f33ff461f85cb457fb4a6ed03b358a5a0615a180`.
- [PR #463 final-head CI run](https://github.com/Bepoadewale/davdeploy/actions/runs/45266750554).
- `docs/tickets/ticket463.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `CODEX_BACKLOG.md`

## Work planned for the PR

1. Advance active source snapshots to PR #463.
2. Record PR #463's KMS plan-policy work without implying AWS lifecycle or
   hosted Nova evidence.
3. Update the monitor record count and retain the no-control-plane-change
   boundary.
4. Preserve historical release and test records.

## Acceptance criteria

- [x] The active handoff, backlog, and capability matrix identify backend
  `main` at PR #463's merge commit.
- [x] KMS plan-policy evidence is recorded as source-only; key-policy,
  consumer binding, billing completeness, and customer-managed-key lifecycle
  evidence remain open.
- [x] Hosted control-plane deployment identity and no-mutation boundary remain
  unchanged.
- [x] The monitor count is reconciled to 41 terminal records and zero active
  operations.
- [x] Protected and unrelated untracked files remain untouched.
- [x] Documentation conventions and `git diff --check` pass.
- [x] The PR head passes all seven checks in CI run
  [45268239876](https://github.com/Bepoadewale/davdeploy/actions/runs/45268239876).

## Acceptance status

The active documentation snapshots and validation record are reconciled on
PR #464. GitHub review and merge state are recorded on the PR.

## Tests / validation performed

- `GITHUB_PR_NUMBER=464 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Final-head CI run 45268239876 — all seven checks passed.

## Evidence files produced

- `CODEX_BACKLOG.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket464.md`

## Boundaries

- Documentation only; do not apply or destroy AWS resources.
- Do not access or change hosted control-plane resources.
- Do not claim customer-managed KMS lifecycle, pricing completeness, Nova
  dispatch, or broad AWS support from PR #463's plan-policy checks.
- Preserve all protected and unrelated untracked local files.

## Follow-up work

Continue with the next dependency-ready implementation package. Keep KMS
consumer/key-policy validation and customer-side lifecycle evidence explicitly
open until separately covered.
