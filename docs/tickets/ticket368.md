# ticket368 — reconcile Nova source and deployed release after PR #367

PR: #368
Branch: `docs/reconcile-nova-release-368`

## Problem / goal

Reconcile the Nova readiness matrix, implementation status, and backlog with
the verified deployment of backend main after PR #367. Preserve the distinction
between deployed control-plane code and the still-disabled customer execution
workflow.

## Current repo state

- Main commit `0481696d8a9aa1c73d789b2076a23f9c07ccc1fb` is deployed after
  PR #367.
- Nova execution gates remain disabled, and no customer Nova plan/workload has
  run.
- PR #318 pricing work remains held pending account-owner direction.

## Research / references used

- `docs/test/test367.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `CODEX_BACKLOG.md`

## Work planned for the PR

- Reconcile current source and hosted release in readiness documentation.
- Record exact Terraform plan/apply IDs, actions, digest, migrations, package
  identity, health, and feature-gate status.
- Preserve the limitations on customer role, pricing, hosted planning, apply,
  runtime secret access, and lifecycle evidence.

## Acceptance criteria

- [x] Current source and hosted release point to exact backend commit
  `0481696d8a9aa1c73d789b2076a23f9c07ccc1fb`.
- [x] The docs record merged-main CI `43137760056`, protected plan
  `43138701232`, exact saved-plan apply `43139500663`, and deployment
  `7726355215`.
- [x] Plan summary, manifest digest, migration outcome, Lambda package identity,
  API health, and Nova feature-gate values match the observed evidence.
- [x] The docs state that #365/#367 do not resolve customer secrets or enable
  runtime secret reads, and that the plan role, remote state, pricing, approval,
  apply, health, recovery, teardown, and composed certification remain gated.
- [x] Pricing PR #318 remains held pending account-owner direction.
- [x] All seven required CI jobs passed on PR head
  `0e43e31a5c689bc1e7e8a6626160a97a6500f916` in run `43142051311`. The final
  ticket-update head must also pass its live GitHub merge-gate checks.

## Acceptance status

- [x] Local release evidence was reconciled against the protected workflow,
  AWS Lambda configuration, and API health response.
- [x] Required docs conventions and whitespace checks pass.
- [x] PR run `43142051311` passed all seven required jobs for head
  `0e43e31a5c689bc1e7e8a6626160a97a6500f916`.
- [ ] Final ticket-update head's required checks must pass before merge.

## Tests / validation performed

- `python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- GitHub Actions run [43142051311](https://github.com/Bepoadewale/davdeploy/actions/runs/43142051311) passed all seven jobs on head `0e43e31a5c689bc1e7e8a6626160a97a6500f916`.
- Runtime plan/apply and post-release evidence are recorded in
  `docs/test/test368.md`.

## Evidence files produced

- `docs/test/test368.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `CODEX_BACKLOG.md`

## Boundaries

Documentation reconciliation only. No Nova execution gate, customer role,
plan, workload, or customer infrastructure was enabled or changed by this PR.

## Follow-up work

Install and verify a customer plan role and complete tenant-scoped remote-state
execution. Pricing remains a held dependency; continue other independent
readiness work without representing it as complete.

## Evidence

- Runtime evidence: [`../test/test368.md`](../test/test368.md).
- Source, release and remaining gate matrix:
  [`../product/EXECUTION_READINESS_MATRIX.md`](../product/EXECUTION_READINESS_MATRIX.md).
