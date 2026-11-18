# ticket431 — reconcile current Nova source and runtime status docs

PR: https://github.com/Bepoadewale/davdeploy/pull/431
Branch: `docs/reconcile-nova-status-431`

## Problem / goal

The top-level backlog and implementation status snapshots predate recent Nova
source merges, and the capability matrix was refreshed before PR #430 merged
and before PR #399's latest synchronization. Reconcile these snapshots without
rewriting historical evidence or confusing backend source with the deployed
control plane.

## Current repo state

Backend `main` is `aef34c0cd6f5fc8a4e87a671246697061f9e9210` (PR #430); hosted
runtime remains at PR #420 commit
`9951caa9244128b1551fea3af66b1bdbf884c800`. PRs #424–#429 are in backend
source, with #429 adding plan-level provider-schema provenance. PR #430 is a
documentation-only matrix refresh. PR #399 remains open/draft at
`81eabbbccb5f47bbb5e0f6929872d675c8a6ee10`, based on `aef34c0`; all seven
current-head checks passed in run `44204640591`. No Nova customer workload has
been applied or certified.

The latest recorded read-only AWS inventory is from 2026-11-17: account
`654654474502` had no tested SageMaker endpoint/model/configuration or active
Terraform operation; inactive Batch definitions and SageMaker lineage evidence
remain preserved. This PR does not perform a new AWS inventory or mutation.

## Research / references used

- `DAVDEPLOY_NOVA_GOAL.md` and private `DAVDEPLOY_NOVA_GOAL_STATUS.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `CODEX_BACKLOG.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/tickets/ticket429.md` and `ticket430.md`

## Work planned for the PR

- Refresh source/runtime and PR #399 snapshots in the matrix and status docs.
- Record #424 and #425–#429 as source-level capabilities that are not deployed
  by PR #420, and keep #430 identified as documentation-only.
- Label read-only AWS state by its check date and retain the distinction between
  source, hosted control-plane, and customer-workload evidence.
- Preserve older dated deployment records as historical snapshots.

## Acceptance criteria

- [x] Current backend `main` and hosted PR #420 are reported separately.
- [x] PR #399 head `81eabbb` and successful run `44204640591` are recorded.
- [x] PR #429 schema evidence is source-only; no customer workload is claimed.
- [x] AWS inventory claims have their 2026-11-17 check date and lineage evidence
  remains marked as retained.
- [x] Documentation conventions and diff checks pass.
- [x] All seven required CI checks pass on status reconciliation commit
  `9cc8690c61aceeea5572c63374db9486a195e3f6` in run `44205925703`.

## Acceptance status

Implementation is complete and verified. All seven required checks passed on
status reconciliation commit `9cc8690c61aceeea5572c63374db9486a195e3f6` in run
`44205925703`. The ticket-only follow-up will receive fresh CI. This PR changes
documentation snapshots only; no AWS, Terraform, or hosted runtime operation
was performed.

## Tests / validation performed

- `GITHUB_PR_NUMBER=431 .venv-pr399/bin/python scripts/check_doc_conventions.py`:
  passed.
- `git diff --check`: passed.
- Final-head GitHub CI run `44205925703` passed all seven checks on
  `9cc8690c61aceeea5572c63374db9486a195e3f6`; the ticket-only follow-up is
  pending.
- No `docs/test/test431.md` is required because no customer workload was part of
  this package.

## Evidence files produced

- `docs/tickets/ticket431.md`
- Updated `CODEX_BACKLOG.md`, `docs/IMPLEMENTATION_STATUS.md`, and
  `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- No `docs/test/test431.md` is required because no customer workload was run.

## Boundaries

Documentation only. No AWS API call, Terraform plan/apply/destroy, hosted
runtime change, credential issuance, or customer workload is included.

## Follow-up work

The designated customer-owned target and approved hosted onboarding path remain
prerequisites for the hosted Nova plan/apply/health/update/recovery/teardown/
absence lifecycle. Keep PR #399 draft with apply and credential gates disabled.
