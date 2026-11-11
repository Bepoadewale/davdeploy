# ticket360 — reconcile Nova source and hosted release evidence

PR: [#360](https://github.com/Bepoadewale/davdeploy/pull/360) (draft; number reserved)
Branch: `docs/reconcile-nova-release-360`
Base: `main`

## Problem / goal

Reconcile the current Nova source and hosted-release status after the November 11
control-plane rollout and the merged API Gateway ownership-policy change.
Preserve the distinction between merged source, deployed package, gated Nova
planning, and the legacy cloud-execution path.

## Current repo state

- Backend `main` is at `d734547a0551e85c5eafcc7349561e3ea7790589` (PR #359).
- PR #358 is deployed by protected Terraform plan `43088843169` and exact saved-
  plan apply `43091195912`; API health and disabled Nova flags are verified.
- PR #359 is merged but its rollout plan has not completed. Run `43095354497`
  ended `startup_failure` with no jobs or logs; a rerun request did not create
  an additional attempt, so there is no active Terraform run.
- The trusted pricing evaluator remains unavailable. PR #318 stays closed and
  held for account-owner direction.

## Research / references used

- Protected Terraform plan/apply records `43088843169` and `43091195912`.
- Read-only AWS Lambda configuration and account identity checks; API
  `https://api.davdeploy.tech/healthz`.
- Existing rollout evidence in `docs/test/test356.md` and merged policy tickets
  #358 and #359.
- `docs/product/EXECUTION_READINESS_MATRIX.md`,
  `docs/IMPLEMENTATION_STATUS.md`, `PROJECT_STATUS.md`, and `CODEX_BACKLOG.md`.

## Work planned for the PR

- Update the current hosted-release entries with exact #358 deployment evidence.
- Add `docs/test/test358.md` with the plan/apply, migration, Lambda package,
  health, feature-gate, and customer-resource boundary evidence.
- Record #359 as merged source pending deployment; do not claim its code is live.
- Reconcile the Nova backlog and execution matrix, retaining all catalogue and
  implementation scope and existing lifecycle gaps.
- State the currently observed Nova feature-gate values separately from legacy
  cloud execution settings.

## Acceptance criteria

- [x] Exact PR, commit, plan/apply run, migration, Lambda package, API health,
  account/region, and runtime flag evidence is recorded.
- [x] Merged source and deployed versions are clearly distinguished.
- [x] Pricing, customer planning, apply, health, recovery, teardown, and scenario
  certification gaps remain explicit.
- [ ] Documentation convention checks and `git diff --check` pass.
- [ ] All required hosted CI checks pass.
- [ ] No infrastructure mutation is performed by this documentation PR.

## Acceptance status

Documentation is updated and locally verified. Hosted CI is pending.

## Tests / validation performed

`GITHUB_PR_NUMBER=360 .venv/bin/python scripts/check_doc_conventions.py` and
`git diff --check` passed locally. `docs/test/test358.md` records protected
control-plane deployment evidence. No AWS mutation occurred for this PR.

## Evidence files produced

This ticket tracks the documentation reconciliation for PR #360.

## Boundaries

This PR records technical release evidence only. It does not enable Nova
planning, change runtime gates, apply Terraform, or alter any customer or AWS
resources. The private strategy and credential notes remain outside both
repositories.

## Follow-up work

Complete PR #359's protected rollout from an exact reviewed saved plan, then
record its deployment separately. Continue trusted pricing only after the
account owner directs how to proceed with held PR #318. Keep Nova customer
planning and lifecycle gates disabled until their independent acceptance work
is complete.
