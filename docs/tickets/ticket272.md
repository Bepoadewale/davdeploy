# ticket272 — Prepare Lambda/API renderer for hosted certification

PR: https://github.com/Bepoadewale/davdeploy/pull/272

Branch: `feat/hosted-serverless-renderer`

## Problem / goal

Add the existing Lambda + HTTP API renderer to the fixed CodeBuild package and typed dispatcher behind a dedicated hosted-certification gate. Keep customer run creation disabled until this renderer has its own source-artifact contract and real hosted AWS evidence.

## Current repo state

CodeBuild dispatch supports the App Runner renderer. The Lambda/API renderer has isolated AWS certification but no customer source-artifact build flow. Service run creation, approval confirmations, and result reconciliation are App Runner-specific. The dispatcher accepts only one typed module per build.

## Research / references used

- `apps/api/src/davdeploy/module_renderers.py`
- `apps/api/src/davdeploy/service.py`
- `apps/api/src/davdeploy/cloud_execution.py`
- `scripts/customer-workload-serverless-api.sh`
- `infrastructure/terraform/customer-workload-serverless-api`
- `docs/product/EXECUTION_READINESS_MATRIX.md`

## Work planned for the PR

Package the checked-in Lambda/API Terraform root and runner, route exact module/operation pairs through the dispatcher only when the hosted-certification flag is explicitly enabled, and prove disabled/mismatched work fails closed. Preserve the App Runner-only service creation gate. Record the missing Lambda source artifact flow and hosted customer lifecycle as follow-up work rather than suggesting this PR enables customer use.

## Acceptance criteria

- [x] The Lambda/API Terraform root and fixed runner are included in the CodeBuild archive.
- [x] The dispatcher has an exact allowlist for Lambda/API plan, destroy-plan, apply, observe, destroy, and cleanup-verification operations.
- [x] Dispatcher tests prove the route is disabled by default and rejects operation mismatches.
- [x] Existing customer run creation remains App Runner-only; the certification gate does not enable customer execution.
- [x] Focused tests and the required isolated local clean-room validation pass.
- [x] CI run 41680224100 passed for implementation commit `afad090`.

## Acceptance status

Complete for this PR's certification-dispatch boundary. The serverless renderer is still unavailable to customer run creation. Durable service integration, Lambda artifact creation, and hosted AWS certification remain follow-up work.

## Tests / validation performed

`make lint` passed. Focused renderer/dispatcher/cloud-execution tests passed: 30 tests. Full `.venv/bin/python -m pytest -q` passed: 362 tests. Shell syntax checks passed for the dispatcher, package builder, and serverless runner. The package builder produced a validation archive containing both renderer roots and scripts. The isolated local clean-room flow passed bootstrap, smoke, API contract, customer-plan E2E, seed, simple/complex/Day-2/degraded demos, policy/readiness failures, trace check, and `make verify` (362 tests plus OpenAPI and Compose checks). `git diff --check` and documentation convention checks passed. CI run 41680224100 passed all seven jobs. This did not exercise hosted CodeBuild or AWS customer resources.

## Evidence files produced

No AWS workload was run by this implementation change. The existing isolated renderer evidence remains in `docs/test/test268.md`; it does not certify hosted CodeBuild dispatch.

## Boundaries

Do not broaden IAM, accept arbitrary scripts or Terraform input, expose this certification flag as a customer control, enable the renderer for customer run creation, or create/delete customer resources in this PR.

## Follow-up work

Implement a repository-commit-pinned Lambda artifact builder and profile-aware durable run records. Then certify plan, apply, health, update/recovery, destroy, and independent absence through hosted CodeBuild with disposable AWS resources. Only after that evidence should customer run creation accept this profile.
