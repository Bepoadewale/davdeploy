# ticket284 — Add controlled serverless certification lifecycle

PR: https://github.com/Bepoadewale/davdeploy/pull/284
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

- [x] Only one `aws-serverless-api` module can be scheduled per run.
- [x] Each lifecycle phase requires the exact eligible prior run and digest.
- [x] Apply and destroy require their own explicit exact confirmations; saved
  plans cannot be submitted more than once.
- [x] Invalid, cross-project, stale, or unapproved requests are rejected before
  CodeBuild dispatch.
- [x] General customer execution remains disabled by default and certification
  requires a workspace allowlist.
- [x] Focused local suite, full `make verify`, docs checks, and Terraform
  validation pass.
- [ ] Required PR CI passes.

## Acceptance status

Typed lifecycle creation and fixture-backed phase chaining are implemented.
Local verification passes; GitHub CI is pending. The repository's local
`make clean-local` cycle was not run because that target removes `.venv`, `.local`
and Docker volumes; the CI clean-runner proof remains the clean integration
check. No AWS workload was deployed, so the renderer remains unavailable for
customer execution.

## Tests / validation performed

Commands and results are recorded in `docs/test/test284.md`. Real AWS lifecycle
certification remains follow-up work.

## Evidence files produced

- `docs/test/test284.md`.

## Boundaries

No multi-module dispatch, arbitrary command, or general customer execution is
introduced by this certification-only flow. The hosted Terraform defaults keep
the certification gate off and the workspace allowlist empty.

## Follow-up work

Run the full hosted AWS lifecycle and record real plan, apply, health, destroy,
and cleanup evidence before considering the Lambda/API renderer for customers.
