# ticket195 — Hosted administrator-pilot role verification

PR: [#196](https://github.com/Bepoadewale/davdeploy/pull/196)
Branch: `fix/execution-broker-assume`

## Problem / goal

The hosted API role could assume a customer discovery role but not the separate
`davdeployExecution-*` role created only for an acknowledged administrator-pilot
connection. Live verification failed before any workload could be submitted.

## Current repo state

The separate execution role, immutable-plan checks, explicit confirmation and
bounded CodeBuild runner already exist. The API broker policy omitted the role
pattern needed to verify that role before a run is allowed.

## Research / references used

Live AWS CloudFormation and Lambda verification evidence, the customer
connection template, and the hosted serverless-control-plane IAM policy.

## Work planned for the PR

- Permit the API control plane to assume the tightly named execution-role
  pattern as well as the existing discovery-role pattern.
- Preserve the discovery-only default and all execution approval gates.
- Add a Terraform contract regression test.

## Acceptance criteria

- [x] The hosted broker policy covers both separately named customer roles.
- [x] Discovery-only connections retain no execution role.
- [x] Regression coverage protects the role-name boundary.

## Acceptance status

Implemented locally; deployment awaits the normal reviewed Terraform workflow.

## Tests / validation performed

`make verify` passed 305 tests. Focused Terraform connection and serverless
runtime tests passed 33 tests.

## Evidence files produced

`docs/test/test195.md` records the live failure classification and local
validation.

## Boundaries

This grants no role to customers, creates no workload, and does not execute
apply or destroy. The customer must still explicitly create the separate
administrator-pilot role and the product must verify it before a bounded runner
can be queued.

## Follow-up work

After the Terraform deployment, re-run the controlled connection verification;
then validate the authenticated plan-only workflow before considering a
cost-bearing workload execution.
