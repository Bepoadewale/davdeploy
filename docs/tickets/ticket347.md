# ticket347 — reconcile deployed customer plan history status

PR: [#347](https://github.com/Bepoadewale/davdeploy/pull/347)
Branch: `docs/reconcile-deployed-plan-history-347`
Base: `main`

## Problem / goal

The readiness matrix still says PR #346 is draft and undeployed. Reconcile it with the merged source, saved Terraform plan, successful apply, Lambda state, migration result and API health evidence. Keep clear that the frontend has not yet consumed the new endpoint and that no Nova customer workload was created.

## Current repo state

- Backend PR #346 is merged as `3a7e5caecfe160ca0f9658fa185c83e050a14e8d`.
- PR CI and merged-main CI passed all required checks.
- The protected apply workflow completed, but the readiness matrix still records the prior deployed commit and says #346 is not deployed.

## Research / references used

- Terraform plan run [42992799853](https://github.com/Bepoadewale/davdeploy/actions/runs/42992799853).
- Terraform apply run [42993697793](https://github.com/Bepoadewale/davdeploy/actions/runs/42993697793).
- Read-only AWS Lambda configuration and API `/healthz` checks performed after apply.
- Backend PR #346 and its evidence at `docs/test/test346.md`.

## Work planned for the PR

- Update the current deployed source/plan/apply snapshot in `EXECUTION_READINESS_MATRIX.md`.
- State that all six Lambda functions are active and successful, migrations passed, and health returned HTTP 200.
- Preserve the limitation that no authenticated customer history request or workload lifecycle was exercised and the frontend has not integrated this endpoint.

## Acceptance criteria

- [x] Matrix cites exact merged source, Terraform plan and apply runs.
- [x] Lambda, migration, health and no-customer-workload evidence is stated accurately.
- [x] History UI integration and all major Nova execution gates remain explicitly unmet.
- [x] Documentation checks pass locally; required GitHub checks remain the merge gate.

## Acceptance status

Documentation is updated and locally validated. Required GitHub checks and
review are pending.

## Tests / validation performed

- `python3.12 scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- GitHub required checks/review: pending.
- Deployment claims are backed by #346 plan/apply workflow runs and read-only
  post-apply checks; no new runtime or AWS operation is part of this PR.

## Evidence files produced

- `docs/test/test347.md`

## Boundaries

Documentation only. No infrastructure, API runtime, deployment, approval, or customer behavior changes.

## Follow-up work

Integrate the deployed revision-history endpoint into the customer history experience through a separate frontend PR, while keeping progress and completion states tied to backend evidence.
