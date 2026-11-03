# ticket283 — Hosted serverless API lifecycle run contract

PR: https://github.com/Bepoadewale/davdeploy/pull/283
Branch: `feat/hosted-serverless-api-run-lifecycle`

## Problem / goal

Connect the already isolated and AWS-tested Lambda + HTTP API renderer to the
hosted durable worker lifecycle for controlled certification. Preserve exact
approved-plan, customer-account, result-integrity, and cleanup checks. Do not
enable multi-module or unrestricted customer execution.

## Current repo state

The hosted CodeBuild dispatcher recognizes `aws-serverless-api`, but
`ProductService.create_cloud_execution_run_for_revision()` rejects every
approved profile except App Runner. The serverless renderer is disabled in the
registry by default. Its Terraform root, artifact builder, runner, result
reconciliation, saved-plan hash checks, and isolated AWS HTTP/cleanup proof
already exist. PRs #277–#280 are deployed; worker lease schema v24 is live.

## Research / references used

- `apps/api/src/davdeploy/cloud_execution.py` — fixed CodeBuild dispatcher input.
- `apps/api/src/davdeploy/module_renderers.py` and `module_contracts.py` — renderer
  binding and supported operations.
- `apps/api/src/davdeploy/service.py` — approved run creation, queue, lease,
  and result reconciliation.
- `scripts/customer-workload-serverless-api.sh` and
  `scripts/customer-serverless-artifact-build.py` — scoped runner operations.
- `infrastructure/terraform/customer-workload-serverless-api` — account guard,
  least-privilege Lambda role, API Gateway, artifact-bound plans, and outputs.
- `docs/product/COMPOSED_EXECUTION_GOAL.md` and
  `docs/product/EXECUTION_READINESS_MATRIX.md`.

## Work planned for the PR

- Make the hosted-certification exception a durable run attribute, not an
  application-process environment switch.
- Ensure only a persisted serverless-certification run context can dispatch the
  checked-in serverless renderer; a caller-supplied environment value alone must
  not grant that ability.
- Then add the one-module certification lifecycle creation/queue contract,
  binding every phase to the approved revision, project, verified connection,
  target account/region, and exact prior artifact or saved plan.
- Preserve phase-specific confirmation, result verification, and durable
  module-instance transitions.
- Keep the serverless API renderer disabled for ordinary customer execution
  until controlled hosted lifecycle certification passes.
- Record local and hosted certification evidence and keep the execution matrix
  accurate.

## Acceptance criteria

- [ ] A reviewed, approved serverless API revision can create only a typed,
  single-module certification run.
- [ ] Apply cannot proceed without its exact successful saved-plan run and
  SHA-256 digest.
- [ ] Observe must match the endpoint produced by the approved apply.
- [ ] Destroy and cleanup verification bind to the same project and plan scope.
- [ ] Invalid or unapproved work never reaches CodeBuild.
- [ ] The ordinary customer execution gate and other renderers remain unchanged.
- [ ] Focused tests, full verification, clean-room validation, and required CI
  pass; live AWS evidence is recorded where a controlled authenticated path is
  available.

## Acceptance status

The persisted worker mode is now forwarded into the trusted adapter context.
The serverless renderer is accepted only when that durable mode and the
`aws-serverless-api` profile match. API run creation and lifecycle phase
validation remain unfinished; the PR stays draft and no customer execution is
enabled.

## Tests / validation performed

The exact commands, results, and any controlled AWS evidence will be recorded in
`docs/test/test283.md`.

## Evidence files produced

- `docs/test/test283.md`.

## Boundaries

No arbitrary Terraform, shell, or user-provided renderer is accepted. This PR
does not enable the Lambda/API renderer for general customer execution and does
not add multi-module scheduling.

## Follow-up work

After module-specific lifecycle certification, make the renderer available
through the same customer-approved graph path. Continue adding certified
renderer bindings and dependency-aware graph execution without exposing AWS
service selection to customers.
