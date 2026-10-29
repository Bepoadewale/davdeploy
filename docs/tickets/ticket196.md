# ticket196 — Hosted administrator-pilot verification policy fix

PR: [#196](https://github.com/Bepoadewale/davdeploy/pull/196)
Branch: `fix/execution-broker-assume`

## Problem / goal

Fix the hosted-policy omission identified by issue #195: the API worker could
not verify the separate `davdeployExecution-*` role from an acknowledged
administrator-pilot connection.

## Current repo state

The hosted control plane has separate discovery and execution brokers, but its
API role only allowed the discovery-role name pattern.

## Research / references used

Live CloudFormation verification evidence, the hosted Terraform IAM policy and
the customer connection contract tests.

## Work planned for the PR

Add the narrow execution-role pattern to the existing API `sts:AssumeRole`
policy and cover both role patterns with a regression test.

## Acceptance criteria

- [x] Only `davdeployDiscovery-*` and `davdeployExecution-*` patterns are
  allowed by the API broker policy.
- [x] Discovery-only access remains the default.
- [x] Local verification passes.

## Acceptance status

Implemented locally; awaiting the reviewed Terraform deployment.

## Tests / validation performed

`make verify` passed 305 tests; focused Terraform connection/runtime tests
passed 33 tests.

## Evidence files produced

`docs/test/test196.md` records this pull request's validation evidence.

## Boundaries

No customer workload, Terraform apply, or destroy operation is run by this PR.

## Follow-up work

Deploy the reviewed policy and re-run the controlled role verification.
