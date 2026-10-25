# ticket146: Read encrypted customer execution result artifacts

PR: #146
Branch: fix/worker-result-artifact-kms

## Problem / goal

The bounded customer executor successfully wrote its encrypted Terraform result,
but the DavDeploy worker could not decrypt it to ingest verified outputs.

## Current repo state

The customer foundation apply has completed in the customer-scoped account. The
only failed control-plane step is result-artifact ingestion.

## Research / references used

- The completed bounded CodeBuild run and its encrypted S3 result artifact.
- Existing serverless Terraform IAM policies and cloud-execution reconciliation.

## Work planned for the PR

- Grant the API worker decrypt-only access to configured execution KMS keys.
- Add an administrator-only retry for exactly the safe artifact-read failure.
- Expose that retry through API, CLI, and MCP without rerunning Terraform.

## Acceptance criteria

- [x] The worker receives only KMS decrypt access for execution artifacts.
- [x] Only the known safe read failure is retryable.
- [x] API, CLI, and MCP expose the same governed reconciliation action.
- [ ] Focused tests and required CI pass.
- [ ] The released worker ingests the existing customer result artifact.

## Acceptance status

Implementation is complete; release and live reconciliation remain.

## Tests / validation performed

- Pending focused tests, Terraform validation, documentation convention checks, and CI.

## Evidence files produced

- Live lifecycle evidence is retained in `docs/test/test130.md`.

## Boundaries

- The action cannot rerun, alter, or apply a Terraform artifact.
- It is limited to an authenticated workspace administrator and the exact
  artifact-read failure state.

## Follow-up work

- Release the serverless control plane and reconcile the completed customer run.
