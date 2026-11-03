# ticket269 — Bind serverless API execution to reviewed plans

PR: pending

Branch: `feat/serverless-api-saved-plan-safety`

## Problem / goal

The Lambda plus HTTP API runner currently creates a saved plan during `plan`, but `apply` builds and applies a new configuration instead of using the exact reviewed artifact. Cleanup verification also relies only on Terraform state. Harden this renderer's plan/apply/destroy lifecycle before it can be registered for customer execution.

## Current repo state

PR #268 certified the isolated renderer root with a real HTTP 200 response and verified deletion. The renderer is not registered for customer execution. The existing App Runner runner has a saved-plan pattern, but the serverless runner does not yet bind apply to the saved artifact.

## Research / references used

Existing `scripts/customer-workload-app-runner-pilot.sh` artifact-bound saved-plan flow; `scripts/customer-workload-serverless-api.sh`; `apps/api/src/davdeploy/cloud_execution.py`; Terraform backend locking and existing execution-result contract.

## Work planned for the PR

Add immutable saved-plan upload and SHA-256 verification for serverless API apply and destroy. Validate required identifiers and artifact digests, write bounded execution results, strengthen cleanup verification using both Terraform state and live AWS absence checks, and add focused contract tests. Keep the renderer out of the customer dispatch registry until the hosted CodeBuild lifecycle is separately validated.

## Acceptance criteria

- [ ] Apply consumes only the exact saved plan and rejects a digest mismatch.
- [ ] Destroy consumes only an approved saved destroy plan.
- [ ] Cleanup checks confirm live Lambda/API absence, not just empty local state.
- [ ] Missing or malformed execution inputs fail before mutation.
- [ ] Focused tests and required CI pass.
- [ ] No customer execution enablement or unrelated AWS changes.

## Acceptance status

In progress.

## Tests / validation performed

Not yet run.

## Evidence files produced

No real AWS workload is created by this PR. If the implementation requires a live workload cycle, add `docs/test/test269.md` before executing it.

## Boundaries

No AWS resources are created by this PR. It does not enable the serverless renderer in production or broaden the execution role.

## Follow-up work

Integrate the hardened renderer through a typed dispatcher, then run a controlled hosted CodeBuild apply, health, destroy, and absence cycle before allowing customer execution.
