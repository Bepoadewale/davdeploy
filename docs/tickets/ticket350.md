# ticket350 — Reconcile Nova broker deployment evidence

PR: [#350](https://github.com/Bepoadewale/davdeploy/pull/350)
Branch: docs/reconcile-nova-broker-deployed-350
Base: main

## Problem / goal

Update the execution-readiness matrix with authoritative merge and deployment evidence for the Nova run-scoped credential broker. Preserve the distinction between deployed control-plane code and a still-disabled, not-yet-used customer planning path.

## Current repo state

PR #348 was merged as `a533d131b50add04b9a9d3501ebba07d76ffbd52` and deployed by exact saved plan/apply runs `43033942614`/`43034517260`. Migrations, six Lambda statuses, deployed package hash/artifact version, broker-off environment flags, and `/healthz` have been verified. The matrix still says PR #348 is under review and not deployed.

## Research / references used

- docs/product/EXECUTION_READINESS_MATRIX.md
- PR #348 and its saved plan/apply runs
- Protected Terraform deployment workflow logs
- AWS Lambda configuration and versioned release artifact metadata

## Work planned for the PR

- Replace stale review status with exact merged source and deployment evidence.
- Record the disabled feature gates, no customer workload, and the remaining pricing/plan/apply/lifecycle gaps.
- Keep the full strategy and operational access notes in the private local status file.

## Acceptance criteria

- [x] Matrix cites exact commit, plan/apply runs, migration result, Lambda status, artifact identity, and health check.
- [x] Matrix explicitly says the Nova broker and runner remain disabled and no customer plan/workload was created.
- [x] Ticket records the exact PR number and deployment evidence.
- [x] Documentation conventions and required CI pass on evidence commit `5d2e15e` in run `43039364305`.

## Acceptance status

Matrix update and source evidence reconciliation are complete. Documentation convention and diff checks passed; all seven required checks passed on `5d2e15e` in run `43039364305`, and current-head Codex review found no major issues. This ticket now records the evidence; its final documentation-only update will receive the merge-gate checks.

## Tests / validation performed

- `python scripts/check_doc_conventions.py` passed.
- `git diff --check` passed.
- PR CI run `43039364305` passed all seven jobs on evidence commit `5d2e15e`.
- Current-head Codex review of `5d2e15e` found no major issues.
- No runtime tests are required for this documentation-only PR. The cited AWS and workflow evidence was collected before opening the PR.

## Evidence files produced

- No runtime evidence file is required because this PR only reconciles source/deployment documentation against already completed workflow and read-only runtime evidence.
- Sources: plan run [43033942614](https://github.com/Bepoadewale/davdeploy/actions/runs/43033942614), apply run [43034517260](https://github.com/Bepoadewale/davdeploy/actions/runs/43034517260), migration success in the apply log, AWS `get-function-configuration` and S3 versioned artifact hash comparison, and `https://api.davdeploy.tech/healthz` HTTP 200.

## Boundaries

No AWS calls or resource changes are part of this documentation PR. It does not enable the Nova broker, plan runner, customer role verification, state API, approval, or apply path.

## Follow-up work

Continue toward trusted costed planning, exact-plan approval, scoped apply, customer health, recovery, teardown, and composed hosted workload certification.
