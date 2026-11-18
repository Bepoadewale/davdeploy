# ticket430 — refresh Nova capability evidence after provider-schema work

PR: https://github.com/Bepoadewale/davdeploy/pull/430
Branch: `docs/nova-schema-evidence-ledger-430`

## Problem / goal

The Nova capability evidence matrix predates PR #429 and its top-level
source/runtime snapshot and PR #399 verification are stale. Update the matrix
to record the new plan-level provider-schema provenance while keeping source
evidence separate from hosted runtime and customer-workload evidence.

## Current repo state

Backend `main` is `b7c15b4940c9a059be8964abff2187f0f05947e7`, including merged
PR #429. The hosted control plane remains at PR #420 commit
`9951caa9244128b1551fea3af66b1bdbf884c800`. PR #429 records the supported
Terraform provider-schema format and canonical schema-document digest in the
plan result and immutable manifest; it is source-only and not deployed. PR #399
remains open/draft at `86584d491a0208cd42c7d91bfd63b9f21f4db09f`, based on
`b7c15b4940c9a059be8964abff2187f0f05947e7`; all seven current-head checks
passed in run `44201512025`. No customer Nova workload has been run.

## Research / references used

- `DAVDEPLOY_NOVA_GOAL.md`, especially packages 1, 4, and 5 and their gates.
- `DAVDEPLOY_NOVA_GOAL_STATUS.md` (private local execution ledger)
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket429.md`
- `docs/tickets/ticket399.md`

## Work planned for the PR

- Update the matrix's source/runtime snapshot and PR #399 current head/run.
- Record PR #429 as merged backend-source evidence, not a hosted deployment.
- Explain that the manifest binds the schema document used for Terraform shape
  validation, but does not establish service semantics, per-module support,
  customer security, pricing, or a hosted lifecycle.

## Acceptance criteria

- [x] Matrix names backend source `b7c15b4` separately from hosted PR #420.
- [x] Matrix records PR #429's plan-level schema format/digest as source-only.
- [x] Matrix records PR #399 head `86584d4` and CI run `44201512025`.
- [x] Matrix still states that no Nova customer workload has been applied or
  certified.
- [x] Documentation conventions and diff checks pass.
- [x] All seven required CI checks pass on the matrix implementation commit
  `1137293e24d3c9e32add585283f96254548f7ef7` in run `44202571991`.

## Acceptance status

Implementation is complete and verified. All seven required checks passed on
matrix implementation commit `1137293e24d3c9e32add585283f96254548f7ef7` in run
`44202571991`. The ticket-only follow-up will receive a fresh CI run. This is
documentation-only; no AWS or Terraform operation was performed.

## Tests / validation performed

- `GITHUB_PR_NUMBER=430 .venv-pr399/bin/python scripts/check_doc_conventions.py`:
  passed.
- `git diff --check`: passed.
- Final-head GitHub CI run `44202571991` passed all seven checks on
  `1137293e24d3c9e32add585283f96254548f7ef7`; the ticket-only follow-up is
  pending.
- No `docs/test/test430.md` is required because no customer workload was part of
  this package.

## Evidence files produced

- `docs/tickets/ticket430.md`
- Updated `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- No `docs/test/test430.md` is required because no customer workload was run.

## Boundaries

Documentation only. No AWS API call, Terraform plan/apply/destroy, hosted
runtime change, credential issuance, or customer workload is included.

## Follow-up work

The designated customer-owned test account/role and approved hosted onboarding
path remain prerequisites for the complete hosted Nova plan/apply/health/update/
recovery/teardown/absence lifecycle. Keep PR #399 draft and its apply and
credential gates disabled.
