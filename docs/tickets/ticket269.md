# ticket269 — Bind serverless API execution to reviewed plans

PR: https://github.com/Bepoadewale/davdeploy/pull/269

Branch: `feat/serverless-api-saved-plan-safety`

## Problem / goal

The Lambda plus HTTP API runner currently creates a saved plan during `plan`, but `apply` builds and applies a new configuration instead of using the exact reviewed artifact. Cleanup verification also relies only on Terraform state. Harden this renderer's plan/apply/destroy lifecycle before it can be registered for customer execution.

## Current repo state

PR #268 certified the isolated renderer root with a real HTTP 200 response and verified deletion. The renderer is not registered for customer execution. The existing App Runner runner has a saved-plan pattern, but the serverless runner does not yet bind apply to the saved artifact.

## Research / references used

Existing `scripts/customer-workload-app-runner-pilot.sh` artifact-bound saved-plan flow; `scripts/customer-workload-serverless-api.sh`; `apps/api/src/davdeploy/cloud_execution.py`; Terraform backend locking and existing execution-result contract.

## Work planned for the PR

Added plan-digest-scoped saved-plan upload and SHA-256 verification for serverless API apply and destroy. The runner checks identifiers and digests, assumes only the expected customer account role, records bounded execution results including artifact and saved-plan hashes, and checks live Lambda, IAM role, HTTP API, and Terraform state absence. Focused contract tests and runtime rejection tests for changed artifacts and saved plans were added. The renderer remains out of the customer dispatch registry until the hosted CodeBuild lifecycle is separately validated.

## Acceptance criteria

- [x] Apply consumes only the exact saved plan and rejects a digest mismatch.
- [x] Destroy consumes only an approved saved destroy plan.
- [x] Cleanup checks confirm live Lambda/API/IAM absence and empty Terraform state.
- [x] Missing or malformed identifiers, digests, and account/role combinations fail before Terraform mutation.
- [x] Focused tests and Terraform validation pass.
- [ ] Updated PR revision passes required CI.
- [x] No customer execution enablement or unrelated AWS changes.

## Acceptance status

In progress.

## Tests / validation performed

`bash -n scripts/customer-workload-serverless-api.sh`; focused pytest for the
serverless renderer contract and artifact/saved-plan digest rejection (4 passed);
Terraform `fmt -check` for both customer and validation roots; Terraform
validation for the isolated validation root; and
`GITHUB_PR_NUMBER=269 python3 scripts/check_doc_conventions.py` all passed.
No AWS resources were created by this PR.

## Evidence files produced

No real AWS workload is created by this PR. If the implementation requires a live workload cycle, add `docs/test/test269.md` before executing it.

## Boundaries

No AWS resources are created by this PR. It does not enable the serverless renderer in production or broaden the execution role.

## Follow-up work

Integrate the hardened renderer through a typed dispatcher, then run a controlled hosted CodeBuild apply, health, destroy, and absence cycle before allowing customer execution.
