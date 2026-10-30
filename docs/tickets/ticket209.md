# ticket209

PR: [#209](https://github.com/Bepoadewale/davdeploy/pull/209)

Branch: `docs/record-scale-path`

## Problem / goal

Record the future cell-based architecture while making the immediate decision
explicit: serve the first roughly 100 users with the cheapest current managed
control plane and preserve the scale boundaries already in the product.

## Current repo state

The scale strategy already describes tenant scope, regional cells and a staged
evolution. It did not state the first-customer cost posture, the trigger for an
ECS migration, or the relationship between the lean present topology and the
future cell design.

## Research / references used

- Existing `docs/strategy/10-scale-and-multi-tenancy.md` scale boundaries.
- Current hosted Terraform defaults: Aurora Serverless v2 can pause at zero
  capacity with a maximum of two ACUs.
- Current account cost data was reviewed only to calibrate the small-customer
  planning range; no resource was changed.

## Work to be done

- Add an architecture and cost decision record to the scale strategy.
- State the first-customer stack, indicative cost boundary, ECS migration
  trigger, and regional-cell direction.

## Acceptance criteria

- [x] The current low-cost topology is distinct from the future architecture.
- [x] The estimate is explicitly non-binding and excludes AI and customer
  workloads.
- [x] The scale direction preserves tenancy, approval and customer-cloud
  security boundaries.

## Acceptance status

Implemented locally; pending documentation CI and review.

## Validation performed

Documentation review and repository documentation conventions CI are pending.

## Evidence files

No customer workload test was performed. This is documentation-only.

## Boundaries

No AWS infrastructure, customer data, pricing configuration, execution path or
application behavior is changed.

## Follow-up work

When real usage exists, replace the planning range with Cost Explorer evidence
and a reviewed capacity model based on active users, requests, jobs and model
usage.
