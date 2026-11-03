# ticket283 — Bind hosted serverless dispatch to durable certification mode

PR: https://github.com/Bepoadewale/davdeploy/pull/283
Branch: `feat/hosted-serverless-api-run-lifecycle`

## Problem / goal

The hosted serverless renderer was gated by a process environment variable.
That made the privileged route dependent on deployment configuration rather
than the durable, auditable execution run. Require the persisted certification
mode and matching renderer profile before the trusted worker can submit the
fixed serverless CodeBuild job. This change does not add customer execution.

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

The planned trust-boundary change is complete:

- Make the hosted-certification exception a durable run attribute, not an
  application-process environment switch.
- Ensure only a persisted serverless-certification run context can dispatch the
  checked-in serverless renderer; a caller-supplied environment value alone must
  not grant that ability.
- The worker forwards `run.mode` from the persisted row into its adapter
  context.
- The registry admits the disabled serverless renderer only for the exact
  `aws-serverless-api` profile and
  `AUTHENTICATED_SERVERLESS_CERTIFICATION` mode.
- CodeBuild receives the certification dispatcher variable only for that
  matching mode.
- Tests prove an environment variable alone or a mismatched run mode cannot
  submit the serverless renderer.

## Acceptance criteria

- [x] A process environment flag alone cannot enable serverless renderer work.
- [x] A matching durable certification mode and renderer profile can dispatch
  only the fixed checked-in serverless job.
- [x] The ordinary customer execution gate and other renderers remain
  unchanged.
- [x] Focused tests, documentation checks, and required CI pass.

## Acceptance status

The durable-mode boundary change and its tests are complete. The follow-up
serverless run-creation API and lifecycle phase validation remain unfinished;
no customer execution is enabled.

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
