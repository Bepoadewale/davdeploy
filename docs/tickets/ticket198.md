# ticket198 — Verify acknowledged pilot execution roles

PR: [#198](https://github.com/Bepoadewale/davdeploy/pull/198)
Branch: `fix/pilot-role-verification-trust`

## Problem / goal

Administrator-pilot verification uses STS to prove that the separately created
execution role belongs to the connected AWS account. The template trusted only
the CodeBuild execution broker, so the hosted API verifier could not make that
proof.

## Current repo state

The API policy permits only the named discovery and execution role patterns.
The execution role already uses a unique per-connection external ID and the
actual workload runner remains the separate CodeBuild broker.

## Research / references used

Live failed verification evidence from the controlled AWS connection, the
CloudFormation template, the hosted IAM policy, and connection lifecycle tests.

## Work planned for the PR

Trust the discovery/API broker alongside the existing execution broker in the
administrator-pilot execution-role trust policy, under the same external-ID
condition, and cover the contract.

## Acceptance criteria

- [x] The CodeBuild execution broker remains trusted.
- [x] The hosted verifier can be trusted for STS identity verification.
- [x] The per-connection external-ID condition remains required.
- [x] The default discovery path remains unchanged.

## Acceptance status

Implemented locally; template publication and controlled stack update follow
the reviewed merge.

## Tests / validation performed

CloudFormation template validation passed. Focused connection and lifecycle
tests passed 12 tests.

## Evidence files produced

`docs/test/test198.md` contains command and boundary evidence.

## Boundaries

No customer workload, apply, or destroy is performed. This changes role trust
only for a pre-execution identity verification protected by the external ID.

## Follow-up work

Publish the immutable template, update the controlled connection stack, and
re-run verification before any authenticated plan-only test.
