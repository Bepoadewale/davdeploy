# ticket154 — Retain live pricing evidence in customer reviews

PR: [#154 — fix: retain live pricing evidence in customer reviews](https://github.com/Bepoadewale/davdeploy/pull/154)
Branch: `fix/live-pricing-evidence-review`

## Problem / goal

Customer reviews retained live inventory counts but discarded the attached AWS Pricing and Cost
Explorer evidence, leaving only a clearly labelled deterministic estimate.

## Current repo state

The verified customer connection has a fresh read-only snapshot with executed AWS catalog and Cost
Explorer evidence. Its new private-repository customer review omits that evidence.

## Research / references used

- Fresh snapshot `0ddbf71e-a0ab-4883-89d0-8b60f1e6d428` from the verified customer connection.
- `ProductService.create_customer_plan_review` review serializer.

## Work planned for the PR

- Include durable pricing evidence in the customer-review inventory snapshot and evidence block.
- Retain the truthful deterministic-estimate label; do not present estimates as AWS bills.

## Acceptance criteria

- [ ] Live pricing evidence reaches customer review content when a verified connection is selected.
- [ ] Fixture snapshots remain explicitly empty rather than being fabricated as live pricing.
- [ ] Tests and CI pass.

## Acceptance status

Implementation in progress.

## Tests / validation performed

- Pending focused customer-plan review regression test.

## Evidence files produced

- `docs/test/test154.md`

## Boundaries

This changes review evidence only. It does not create cloud resources, apply Terraform, or destroy
customer resources.

## Follow-up work

Create and approve a fresh private-repository review after deployment, then continue the guarded
service lifecycle.
