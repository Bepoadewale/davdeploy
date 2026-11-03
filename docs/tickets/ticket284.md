# ticket284 — Add controlled serverless certification lifecycle

PR: pending
Branch: `feat/serverless-certification-lifecycle`

## Problem / goal

The hosted worker can safely accept a persisted serverless certification run mode,
but the product has no typed API flow to create, approve, execute, and reconcile
its serverless lifecycle phases. Add a bounded single-renderer certification
flow without enabling general customer execution.

## Current repo state

PR #283 is merged. Existing serverless Terraform, artifact packaging, CodeBuild
dispatch, result integrity checks, and cleanup verification are present. The
serverless renderer remains disabled for ordinary customer execution.

## Research / references used

- `apps/api/src/davdeploy/service.py` — approved revision and worker lifecycle.
- `apps/api/src/davdeploy/cloud_execution.py` — certification-mode dispatcher.
- `apps/api/src/davdeploy/domain.py` and `main.py` — cloud execution request API.
- `scripts/customer-workload-serverless-api.sh` — plan/apply/observe/destroy contract.
- `scripts/customer-serverless-artifact-build.py` — pinned artifact contract.
- `docs/product/EXECUTION_READINESS_MATRIX.md`.

## Work planned for the PR

- Add a typed, workspace-authorized single-module serverless certification request.
- Chain build, plan, apply, observe, destroy-plan, destroy, and cleanup verification
  only to matching prior runs and exact artifact or saved-plan digests.
- Keep each run bound to the approved digest, verified connection, account,
  region, and project.
- Keep the ordinary customer execution gate disabled.
- Add negative tests, focused verification, evidence, and truthful status updates.

## Acceptance criteria

- [ ] Only one `aws-serverless-api` module can be scheduled per run.
- [ ] Each lifecycle phase requires the exact eligible prior run and digest.
- [ ] Apply and destroy require their own explicit exact confirmations.
- [ ] Invalid, cross-project, stale, or unapproved requests never reach CodeBuild.
- [ ] General customer execution remains disabled.
- [ ] Focused tests and required CI pass.

## Acceptance status

Implementation not started.

## Tests / validation performed

Commands and results will be recorded in `docs/test/test284.md` if a controlled
AWS workload cycle is performed.

## Evidence files produced

- `docs/test/test284.md` if required for a workload run.

## Boundaries

No multi-module dispatch, arbitrary command, or general customer execution is
introduced by this certification-only flow.

## Follow-up work

Run the full hosted AWS lifecycle and record real plan, apply, health, destroy,
and cleanup evidence before considering the Lambda/API renderer for customers.
