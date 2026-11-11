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
- PR #359 is merged but its rollout plan has not completed. The first protected
  plan attempt ended before any job was created; the same run is being retried.
- The trusted pricing evaluator remains unavailable. PR #318 stays closed and
  held for account-owner direction.

## Work planned for the PR

- Update the current hosted-release entries with exact #358 deployment evidence.
- Record #359 as merged source pending deployment; do not claim its code is live.
- Reconcile the Nova backlog and execution matrix, retaining all catalogue and
  implementation scope and existing lifecycle gaps.
- State the currently observed Nova feature-gate values separately from legacy
  cloud execution settings.

## Acceptance criteria

- [ ] Exact PR, commit, plan/apply run, migration, Lambda package, API health,
  account/region, and runtime flag evidence is recorded.
- [ ] Merged source and deployed versions are clearly distinguished.
- [ ] Pricing, customer planning, apply, health, recovery, teardown, and scenario
  certification gaps remain explicit.
- [ ] Documentation convention checks and `git diff --check` pass.
- [ ] All required hosted CI checks pass.
- [ ] No infrastructure mutation is performed by this documentation PR.

## Acceptance status

Bootstrap only; documentation changes and validation are pending.

## Tests / validation performed

None yet.

## Evidence files produced

This ticket tracks the documentation reconciliation for PR #360.

## Boundaries

This PR records technical release evidence only. It does not enable Nova
planning, change runtime gates, apply Terraform, or alter any customer or AWS
resources. The private strategy and credential notes remain outside both
repositories.
