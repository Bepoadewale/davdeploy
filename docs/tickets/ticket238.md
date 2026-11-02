# ticket238 — Platform module batch

PR: [#238](https://github.com/Bepoadewale/davdeploy/pull/238)

Branch: `feat/module-batch-06-platform`

## Problem / goal

Add EKS, EC2 autoscaling, VPC, VPN and multi-region DNS Terraform modules
alongside their disabled internal module definitions.

## Current repo state

Stacked on #237.

## Research / references used

Existing DavDeploy module contracts and AWS service boundaries.

## Work planned for the PR

Add five platform module definitions and reusable module roots, correct the
Batch identifier, and reconcile registry paths/resources with actual modules.

## Acceptance criteria

- [x] Five module definitions exist and default disabled.
- [x] Batch module identifier is corrected.
- [x] Registry paths and resource inventories match real module roots.
- [ ] Full platform lifecycle tests remain disabled because EKS, NAT, VPN and
  multi-region DNS require longer-lived network, external endpoint and cost
  controls.

## Acceptance status

Implementation is complete. All platform entries remain disabled until their
network, recovery, cost and workload-specific validation evidence exists.

## Tests / validation performed

Terraform formatting and provider-schema validation are run for the safe
module roots. No expensive or externally coupled platform deployment is
represented as tested.

## Evidence files produced

`docs/test/test238.md`

## Boundaries

No AWS changes are enabled.

## Follow-up work

Validate, enable and merge the stacked batches in order.
