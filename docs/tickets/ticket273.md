# ticket273 — Build pinned Lambda source artifacts safely

PR: https://github.com/Bepoadewale/davdeploy/pull/273

Branch: `feat/serverless-customer-artifact`

## Problem / goal

The Lambda/API renderer accepts an immutable ZIP artifact and digest, but DavDeploy has no bounded way to construct that artifact from the source repository selected in an approved plan. Add a deterministic, repository-commit-pinned artifact builder for the first Lambda source contract. Do not enable customer execution as part of this ticket.

## Current repo state

PR #272 packages the Lambda/API Terraform root and runner and adds a default-off typed certification dispatch route. Customer run creation remains App Runner-only. The existing Lambda runner expects `DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI` and `DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256`.

## Research / references used

- `apps/api/src/davdeploy/module_renderers.py`
- `apps/api/src/davdeploy/cloud_execution.py`
- `scripts/customer-workload-dispatcher.sh`
- `scripts/customer-workload-serverless-api.sh`
- `infrastructure/terraform/customer-workload-serverless-api`
- `docs/product/EXECUTION_READINESS_MATRIX.md`

## Work planned for the PR

Define and implement a no-build-command source contract that packages the root `index.py` Lambda entrypoint plus regular files in an optional `vendor/` directory from a full-SHA public GitHub commit. Vendor files are placed at the ZIP root for Python import resolution. Reject mutable refs, unsafe file types/paths, oversized archives, and arbitrary build commands. Produce a digest-bound artifact plus result evidence in the connection-scoped S3 prefix. Keep the operation opt-in for hosted certification; do not add a customer run-creation or deploy path.

## Acceptance criteria

- [x] Source repository is canonical and pinned to a full immutable commit.
- [x] Builder packages only the allowed entrypoint and vendor tree, with path/symlink and size validation.
- [x] No customer-provided shell/build commands execute.
- [x] Artifact is uploaded to the expected tenant/plan-scoped key and SHA-256 is recorded; server-side encryption is verified.
- [x] CodeBuild dispatch is typed, operation-specific, and disabled by default.
- [ ] Focused tests and full local clean-room validation pass.
- [ ] CI passes.
- [x] Customer run creation remains App Runner-only.

## Acceptance status

Implementation and focused verification are complete. The isolated clean-room run and PR CI remain.

## Tests / validation performed

`make lint` passed. Focused artifact-builder, renderer, dispatcher, and cloud-execution tests passed: 35 tests. Full `.venv/bin/python -m pytest -q` passed: 367 tests. Shell syntax, Python compilation, documentation conventions, and `git diff --check` passed. The executor package builder included the new fixed artifact script and Lambda/API renderer files. No real AWS artifact upload was performed.

## Evidence files produced

No AWS workload is planned for this implementation PR. A real hosted artifact build and Lambda lifecycle certification will require a separate disposable AWS evidence PR.

## Boundaries

Do not run source build scripts, install arbitrary customer dependencies, broaden CodeBuild IAM, use mutable repository references, or enable Lambda/API customer deployment. Do not create or delete customer cloud resources.

## Follow-up work

Integrate artifact-build state with profile-aware plan review, saved-plan approval, apply, health observation, update/recovery, destroy, and cleanup evidence. Then run a real hosted CodeBuild certification cycle before exposing this renderer to customer run creation.
