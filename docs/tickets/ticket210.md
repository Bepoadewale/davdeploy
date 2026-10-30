# ticket210

PR: [#210](https://github.com/Bepoadewale/davdeploy/pull/210)

Branch: `docs/record-aurora-warm-threshold`

## Problem / goal

Record the early-hosting decision for Aurora Serverless v2: when to favour
zero-cost idle pause and when to hold 0.5 ACU for consistent first-use latency.

## Current repo state

The hosted control plane uses Aurora Serverless v2 with a zero-ACU minimum,
two-ACU maximum, and a 15-minute auto-pause interval. The scale strategy
described the early hosted shape but did not record this availability/cost
tradeoff or make clear that it is independent of an ECS migration.

## Research / references used

- AWS Aurora Serverless v2 auto-pause documentation.
- Deployed cluster configuration and read-only seven-day capacity metrics.
- Current US East Aurora Serverless v2 price catalog for the 0.5-ACU estimate.

## Work planned for the PR

- Add the Aurora availability decision and cost boundary to the scale strategy.
- State that Lambda remains the default API/worker runtime at early scale.

## Acceptance criteria

- [x] The zero-ACU and 0.5-ACU tradeoff is documented accurately.
- [x] The 0.5-ACU estimate is labelled indicative and excludes other services.
- [x] The document does not imply an ECS migration is required.

## Acceptance status

Implemented locally; pending documentation CI and review.

## Tests / validation performed

Documentation conventions validation is pending.

## Evidence files produced

No customer workload test was performed. This is documentation-only.

## Boundaries

This PR changes no Aurora, Lambda, Terraform, customer, authentication, or
billing configuration.

## Follow-up work

Revisit the setting after real-customer latency evidence. Any capacity change
requires a reviewed Terraform plan and post-change latency/cost verification.
