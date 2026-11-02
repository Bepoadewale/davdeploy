# ticket238 — Platform module batch

PR: [#238](https://github.com/Bepoadewale/davdeploy/pull/238)

Branch: `feat/module-batch-06-platform`

## Problem / goal

Add disabled EKS, EC2 autoscaling, VPC, VPN and multi-region DNS modules.

## Current repo state

Stacked module batch; validation is deferred by request.

## Research / references used

Existing DavDeploy module contracts and AWS service boundaries.

## Work planned for the PR

Add five platform module definitions and correct the Batch identifier.

## Acceptance criteria

- [x] Five module definitions exist and default disabled.
- [x] Batch module identifier is corrected.
- [ ] Validation deferred.

## Acceptance status

Implementation complete; validation deferred.

## Tests / validation performed

None by explicit request.

## Evidence files produced

`docs/test/test238.md`

## Boundaries

No AWS changes are enabled.

## Follow-up work

Validate, enable and merge the stacked batches in order.
