# ticket275 — Isolate Lambda renderer state by project

PR: https://github.com/Bepoadewale/davdeploy/pull/275

Branch: `feat/serverless-project-isolation`

## Problem / goal

The Lambda/API runner currently keys Terraform state only by cloud connection and uses a default service name based on that connection. Two projects connected to the same AWS account could therefore share one Terraform state and collide on resource names. Its artifact and result object keys are also not project-scoped.

Make the existing Lambda renderer's state key, resource tags, artifact key, and result key explicitly project-scoped. This prepares a safe project boundary before adding any Lambda customer run-creation flow.

## Current repo state

PR #267 added the isolated Lambda/API Terraform root and runner. PR #273 added a bounded, commit-pinned artifact builder. PR #274 added exact run/digest/connection/operation result reconciliation. The product API still rejects Lambda customer execution; this PR does not change that gate.

## Research / references used

- `scripts/customer-workload-serverless-api.sh`
- `scripts/customer-serverless-artifact-build.py`
- `infrastructure/terraform/customer-workload-serverless-api`
- `apps/api/src/davdeploy/service.py`
- `apps/api/src/davdeploy/cloud_execution.py`
- `tests/test_serverless_artifact_builder.py`
- `docs/product/EXECUTION_READINESS_MATRIX.md`

## Work planned for the PR

- Require and validate a stable project identifier in serverless artifact and lifecycle contexts.
- Put artifact, saved-plan, result, and Terraform state objects under a connection/project prefix.
- Use a project-stable Lambda/API resource name and add project ownership tags.
- Update package contracts and tests; reject missing or mismatched project scope.
- Keep Lambda customer run creation disabled.

## Acceptance criteria

- [x] Missing, malformed, or mismatched project IDs fail before S3 writes or Terraform execution.
- [x] Two projects in one cloud connection resolve to distinct state, artifact, result, and resource identities.
- [x] Lambda/API resources carry the approved connection and project ownership tags.
- [x] Artifact and runner contract tests cover the new paths and reject cross-project scope.
- [ ] Focused tests, full local clean-room cycle, and CI pass.
- [x] No customer execution path is enabled.

## Acceptance status

Implementation is complete locally. Focused validation and full repository
verification and a fresh isolated clean-room cycle passed. PR CI remains pending.

## Tests / validation performed

- `bash -n scripts/customer-workload-serverless-api.sh scripts/customer-workload-dispatcher.sh` — passed.
- `python3 -m py_compile scripts/customer-serverless-artifact-build.py` — passed.
- `.venv/bin/ruff check scripts/customer-serverless-artifact-build.py apps/api/src/davdeploy/service.py tests/test_serverless_artifact_builder.py tests/test_serverless_renderer_contract.py tests/test_serverless_runner_safety.py tests/test_cloud_execution.py` — passed.
- `.venv/bin/python -m pytest tests/test_serverless_artifact_builder.py tests/test_serverless_renderer_contract.py tests/test_serverless_runner_safety.py tests/test_cloud_execution.py -q` — 41 passed, one Starlette deprecation warning.
- `terraform -chdir=infrastructure/terraform/customer-workload-serverless-api init -backend=false -input=false` and `terraform ... validate` — passed; no cloud backend or account used.
- `make verify` — passed: configuration boundary, Ruff, 380 tests, OpenAPI snapshot, and Compose configuration; one Starlette deprecation warning.
- `git diff --check` and Terraform formatting check — passed.
- Fresh clean-room cycle at commit `fdd9e6c`, using isolated worktree
  `/tmp/davdeploy-cleanroom-pr275-20261103` and Compose project
  `davdeploy-pr275-20261103` — passed: bootstrap, smoke, API contract,
  customer-plan E2E, simple/complex/degraded/Day-2/failure/readiness demos,
  trace check, full verification (380 tests), OPA (3/3), Terraform offline
  validation, Kubernetes render, and scoped cleanup. This is local fixture
  evidence, not AWS renderer certification.
- GitHub PR checks — pending.

## Evidence files produced

See `docs/test/test275.md`. No AWS workload is planned for this PR. Project-isolated hosted lifecycle certification remains a follow-up.

## Boundaries

Do not create or delete AWS resources, broaden IAM, enable Lambda customer execution, or introduce an environment field that the product flow does not yet choose explicitly.

## Follow-up work

Add a durable, administrator-authorized Lambda run flow that derives this stable project scope from the approved plan, validates source artifacts, and connects saved-plan review, apply, observation, destroy, and cleanup. Certify the hosted flow with disposable AWS resources before customer execution is enabled.
