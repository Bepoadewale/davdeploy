# ticket272 — Integrate Lambda/API renderer with hosted execution

PR: pending

Branch: `feat/hosted-serverless-renderer`

## Problem / goal

Route the existing Lambda + HTTP API renderer through durable approved customer plan runs, CodeBuild dispatch, and result reconciliation. Keep it disabled for customer execution until real hosted AWS certification completes.

## Current repo state

CodeBuild dispatch supports only the enabled App Runner renderer. The Lambda/API renderer has isolated AWS certification but remains disabled. Service run creation, approval confirmations, and result reconciliation are App Runner-specific.

## Research / references used

- `apps/api/src/davdeploy/module_renderers.py`
- `apps/api/src/davdeploy/service.py`
- `apps/api/src/davdeploy/cloud_execution.py`
- `scripts/customer-workload-serverless-api.sh`
- `infrastructure/terraform/customer-workload-serverless-api`
- `docs/product/EXECUTION_READINESS_MATRIX.md`

## Work planned for the PR

Implement a typed Lambda/API execution contract from approved plan through result evidence. Persist operation-specific artifact and plan references, dispatch only checked-in runner operations, reconcile health/apply/destroy outputs, reject unsupported operations and stale digests, and retain fail-closed default gates.

## Acceptance criteria

- [ ] Lambda/API plan, apply, observe, destroy-plan, destroy, and cleanup operations have exact typed operation mappings.
- [ ] Worker run creation and result reconciliation are profile-aware without weakening App Runner checks.
- [ ] Artifact, saved-plan, digest, account, connection and state paths are bound and validated.
- [ ] The new renderer remains disabled for customers pending hosted AWS certification.
- [ ] Focused tests, clean-room validation as required, and CI pass.

## Acceptance status

In progress.

## Tests / validation performed

Not yet run.

## Evidence files produced

No customer workload run is authorized by this implementation PR. Add PR-numbered real AWS evidence only in a dedicated certification PR.

## Boundaries

Do not broaden IAM, accept arbitrary scripts or Terraform input, enable the renderer by default, or create/delete customer resources in this PR.

## Follow-up work

Deploy and certify this renderer through the hosted CodeBuild path with disposable AWS resources, then enable supported Lambda/API plans only after successful health, update/recovery, destroy and independent absence evidence.
