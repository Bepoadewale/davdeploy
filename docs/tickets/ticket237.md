# ticket237 — AI module batch

PR: [#237](https://github.com/Bepoadewale/davdeploy/pull/237)

Branch: `feat/module-batch-05-ai`

## Problem / goal

Add Bedrock, RAG, SageMaker, Kinesis and Batch Terraform modules alongside
their disabled internal module definitions.

## Current repo state

Stacked on #236.

## Research / references used

Existing DavDeploy module contracts and AWS service boundaries.

## Work planned for the PR

Add five AI, stream and batch module definitions and Terraform module roots.

## Acceptance criteria

- [x] Five module definitions exist and default disabled.
- [x] Focused Terraform schema validation completed.
- [ ] Bedrock, RAG, SageMaker, Batch and Kinesis require model, data,
  networking and workload-specific validation and remain explicitly disabled.

## Acceptance status

Implementation is complete. The registry remains disabled pending module-level
policy and live-workload validation.

## Tests / validation performed

`terraform fmt` and focused Terraform validation, plus a disposable Kinesis
root prepared for later live execution.

## Evidence files produced

`docs/test/test237.md`

## Boundaries

No customer-facing AWS changes are enabled.

## Follow-up work

Continue stacked module batches.
