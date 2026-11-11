# ticket357 — reconcile Nova readiness through PR #356 deployment

PR: [#357](https://github.com/Bepoadewale/davdeploy/pull/357) (draft)
Branch: `docs/reconcile-nova-release-357`
Base: `main`

## Problem / goal

The readiness matrix and root project status still referenced older hosted
control-plane releases. PRs #354–#356 have since been merged and deployed,
including protected plan-log redaction and actual-plan IAM, SQS, and Lambda
invocation policy controls. The repository needs exact source, plan, apply,
deployment, runtime-gate, and health evidence without implying that customer
Nova execution is enabled.

## Current repo state

- Backend `main` is `11e66e878933a69638128a8bab80115c051d230a` (PR #356),
  deployed by protected apply run `43082767507`.
- All six control-plane Lambda functions are Active/Successful, and
  `https://api.davdeploy.tech/healthz` returned HTTP 200.
- Customer plan-runner, role-verification, credential-broker, plan-review,
  state API, and hosted-certification gates remain false or absent.
- No Nova-generated customer plan or workload has been applied or certified.

## Research / references used

- [PR #356](https://github.com/Bepoadewale/davdeploy/pull/356) and its
  final-head CI run `43081014081`.
- [Protected plan run 43081890092](https://github.com/Bepoadewale/davdeploy/actions/runs/43081890092)
  and [apply run 43082767507](https://github.com/Bepoadewale/davdeploy/actions/runs/43082767507).
- `docs/test/test356.md` and read-only AWS Lambda/health checks performed
  after the apply completed.

## Work planned for the PR

- Record the PR #356 protected plan and apply, manifest digest, six Lambda
  package identity, migration result, and API health in `docs/test/test356.md`.
- Reconcile `PROJECT_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`,
  `docs/product/EXECUTION_READINESS_MATRIX.md`, and `CODEX_BACKLOG.md` with
  the latest deployed source and its remaining customer-workflow blockers.
- Mark ticket #356 as merged and deployed with its final-head CI evidence.

## Acceptance criteria

- [x] Latest deployed commit, plan/apply runs, artifact digest, migrations,
  Lambda identity, runtime gates, and health are recorded from observed data.
- [x] Current status distinguishes deployed control-plane safeguards from
  disabled customer plan/apply/lifecycle capability.
- [x] Held pricing work and customer-role verification limitations remain
  explicit; no capability or scenario is removed from the matrix.
- [x] Documentation conventions and diff checks pass.
- [ ] Required hosted CI passes on the final PR head.

## Acceptance status

Documentation reconciliation is complete and locally checked. Required
hosted CI and current-head review are pending.

## Tests / validation performed

- `GITHUB_PR_NUMBER=357 python3.12 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- No AWS calls, Terraform plan/apply, or customer-resource changes are in
  scope for this documentation PR.

## Evidence files produced

- `docs/test/test356.md` contains the protected release and post-deployment
  checks for PR #356.
- The readiness and status documents link to the exact workflow evidence.

## Boundaries

This is documentation only. It does not enable the Nova plan runner, customer
role verification, pricing, plan approval, customer apply, health, recovery,
or teardown.

## Follow-up work

Continue with the plan-only customer-role installation/effective-permission
verification and durable hosted plan path. Regional pricing work remains
held pending account-owner direction. Preserve all current approval and
execution gates until their evidence is complete.
