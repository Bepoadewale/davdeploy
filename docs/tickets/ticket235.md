# ticket235 — Data module batch

PR: [#235](https://github.com/Bepoadewale/davdeploy/pull/235)

Branch: `feat/module-batch-03-data`

## Problem / goal

Add Aurora PostgreSQL, DynamoDB, Redis, OpenSearch and EFS Terraform modules
alongside their disabled internal module definitions.

## Current repo state

Stacked on module batches #233 and #234.

## Research / references used

Existing DavDeploy module contracts and AWS service boundaries.

## Work planned for the PR

Add five data module definitions and reusable Terraform module roots.

## Acceptance criteria

- [x] Five data module definitions exist and default disabled.
- [x] All five module roots format and validate through the AWS provider schema.
- [ ] Real lifecycle validation for private-network data services requires an
  isolated VPC and longer-lived, service-specific test windows; it is not used
  as evidence of customer deployment readiness in this PR.

## Acceptance status

Implementation is complete. Only the DynamoDB disposable lifecycle is suitable
for this low-cost test root; the other modules deliberately remain disabled.

## Tests / validation performed

`terraform fmt` and focused Terraform validation; DynamoDB lifecycle evidence
is recorded in `docs/test/test235.md` once teardown completes.

## Evidence files produced

`docs/test/test235.md`

## Boundaries

No customer-facing AWS changes are enabled. Private data modules require a
reviewed network, service-specific recovery design and controlled validation.

## Follow-up work

Continue stacked module batches.
