# ticket369 — record the plan-role verification gate release

PR: #369  
Branch: `docs/plan-role-verification-release`

## Problem / goal

Record the exact protected Terraform release that enabled only Nova customer
plan-role trust/account verification, and reconcile the readiness docs without
claiming customer planning or execution is available.

## Current repo state

- Backend source is commit `8cebf39f700309fbb57c1b307c18026204be844d`.
- The control-plane plan/apply for that commit succeeded; role verification is
  enabled while plan worker, broker, reviews, state API, and hosted
  certification remain disabled.
- No customer plan role has been installed, and no Nova customer plan or
  workload has been run.
- Regional pricing and exact cost-bound approval remain incomplete. Pricing
  PR #318 is held pending account-owner direction.

## Research / references used

- Protected Terraform plan run `43144381303` and exact saved-plan apply run
  `43145180803`, deployment `7727105514`.
- AWS Lambda configuration for all six control-plane functions and
  `https://api.davdeploy.tech/healthz`.
- `docs/product/EXECUTION_READINESS_MATRIX.md`,
  `docs/IMPLEMENTATION_STATUS.md`, and `CODEX_BACKLOG.md`.
- The IAM condition in
  `infrastructure/terraform/serverless-control-plane/main.tf` and feature
  flag variable mapping in the protected Terraform workflow.

## Work planned for the PR

- [x] Record plan actions, saved-plan digest, exact apply/deployment, migration
  result, deployed Lambda package identity, API health, and individual Nova
  feature-gate status.
- [x] Explain the narrow role-name, external-ID, and verification-session
  conditions; preserve the distinction between identity verification and
  effective-permission attestation.
- [x] Reconcile the execution matrix, implementation status, and backlog.
- [x] Keep the full private Nova strategy and local access details outside the
  repository.

## Acceptance criteria

- [x] Documentation matches the exact saved-plan run and successful apply.
- [x] All six Lambda states, code identity, migration result, and API health
  match the observed release.
- [x] The docs state that runner, broker, plan reviews, state API, and hosted
  certification remain disabled and no Nova customer plan/workload ran.
- [x] The docs state that verification checks role trust/account identity and
  does not prove effective permissions.
- [x] Pricing PR #318 remains held; no customer execution readiness is
  overstated.
- [x] All seven required GitHub checks passed on final documented head
  `2a92fc963b95ef41a058ed875c607360aa2bdde7` in run `43146534499`. The ticket
  records this evidence; this resulting head must itself pass required CI.

## Acceptance status

- [x] Exact plan/apply and post-deployment runtime evidence recorded.
- [x] Readiness documentation preserves the role-verification boundary.
- [x] All seven checks passed in run `43146534499` on head
  `2a92fc963b95ef41a058ed875c607360aa2bdde7`; this ticket update is subject
  to the required final-head CI run.

## Tests / validation performed

- Read-only post-apply Lambda configuration and API health checks passed.
- Exact apply workflow run `43145180803` passed; migration verification
  succeeded.
- `python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- GitHub Actions run
  [43146534499](https://github.com/Bepoadewale/davdeploy/actions/runs/43146534499)
  passed all seven required jobs on head
  `2a92fc963b95ef41a058ed875c607360aa2bdde7`.
- The evidence update must pass all seven checks on its final PR head before
  merge.

## Evidence files produced

- `docs/test/test369.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `CODEX_BACKLOG.md`

## Boundaries

This PR changes documentation only. The corresponding role-verification
control-plane deployment is already complete and recorded as evidence. Do not
enable additional gates through this PR.

## Follow-up work

Complete authenticated customer role installation and live trust/account
verification, tenant-scoped remote-state integration, pricing, and then the
remaining hosted plan/apply/lifecycle proof.
