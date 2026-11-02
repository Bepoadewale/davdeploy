# ticket240 — Data module batch reopen

PR: [#240](https://github.com/Bepoadewale/davdeploy/pull/240)

Branch: `feat/module-batch-03-data`

## Problem / goal

Merge the data-service Terraform module batch after GitHub closed dependent
draft #235 when the delivery base merged.

## Current repo state

Delivery batch #239 is merged. This PR supersedes closed #235.

## Research / references used

AWS Terraform provider schemas and the existing private-network module patterns.

## Work planned for the PR

Merge reusable Aurora PostgreSQL, DynamoDB, Redis, OpenSearch and EFS roots.

## Acceptance criteria

- [x] Five data service module roots exist and remain disabled in the registry.
- [x] Focused schema validation evidence is retained.

## Acceptance status

Ready for CI.

## Tests / validation performed

See `docs/test/test240.md` and source evidence `docs/test/test235.md`.

## Evidence files produced

`docs/test/test240.md`

## Boundaries

No customer data service is enabled. Private-network and recovery validation is
required before any module can be enabled.

## Follow-up work

Run controlled, service-specific lifecycle and recovery tests for each module.
