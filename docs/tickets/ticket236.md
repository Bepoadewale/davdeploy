# ticket236 — Events module batch

PR: [#236](https://github.com/Bepoadewale/davdeploy/pull/236)

Branch: `feat/module-batch-04-events`

## Problem / goal

Add SQS, EventBridge, Step Functions, SNS and SES Terraform modules alongside
their disabled internal module definitions.

## Current repo state

Stacked module batch with a disposable, isolated AWS validation root.

## Research / references used

Existing DavDeploy module contracts and AWS service boundaries.

## Work planned for the PR

Add five event and notification module definitions and Terraform module roots.

## Acceptance criteria

- [x] Five module definitions exist and default disabled.
- [x] Focused Terraform schema validation completed.
- [ ] SES DNS verification and workflow-specific Step Functions validation are
  deliberately separate from this disposable root.

## Acceptance status

Implementation is complete. The registry remains disabled until each service
has its own execution policy and controlled lifecycle evidence.

## Tests / validation performed

`terraform fmt` and `terraform validate`, with a disposable SQS/EventBridge/SNS
lifecycle root.

## Evidence files produced

`docs/test/test236.md`

## Boundaries

No customer-facing AWS changes are enabled.

## Follow-up work

Continue stacked module batches.
