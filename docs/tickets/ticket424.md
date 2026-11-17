# ticket424 — price the bounded Aurora PostgreSQL Serverless v2 plan

PR: pending
Branch: `feat/aurora-serverless-pricing-424`

## Problem / goal

The Nova cost evaluator currently blocks `aws_rds_cluster` and `aws_rds_cluster_instance` as unpriced. The checked-in `modules/aurora-postgres` root provisions an Aurora PostgreSQL Serverless v2 writer, so the relational-data scenario cannot become approval-eligible even when the rest of the proposal is supported. Add a narrowly bounded, assumption-bound regional price calculation for that exact shape. Unsupported cluster modes, readers, storage modes, unknown cost drivers, and missing usage assumptions must continue to block approval.

## Current repo state

- Backend `main` is `8c7f1deab9e9b9865a25d0fffaf87be2066b8ea4` (PR #423); PR #422 role-profile verification is source-only and not deployed.
- The hosted control plane remains at PR #420. No customer Nova plan or workload has been applied or certified.
- `generated_plan_pricing.py` covers selected MySQL RDS, but not the `modules/aurora-postgres` cluster or Serverless v2 capacity.
- AWS pricing must come from exact regional Price List products; customer-provided quantities may be persisted, but prices and SKU identifiers must never come from model output.

## Research / references used

- `apps/api/src/davdeploy/generated_plan_pricing.py`
- `apps/api/src/davdeploy/domain.py`
- `apps/api/src/davdeploy/module_implementations.py`
- `infrastructure/terraform/modules/aurora-postgres/main.tf`
- `tests/test_generated_plan_pricing.py`
- Official AWS Aurora pricing: https://aws.amazon.com/rds/aurora/pricing/
- Official AWS Price List API documentation: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-price-list-query-api.html

## Work planned for the PR

- Define trusted usage assumptions for Aurora storage, standard I/O, and billable backup overage.
- Add exact regional Price List lookups for Serverless v2 ACU-hours, Aurora Standard storage, I/O requests, and backup overage.
- Price only one Aurora PostgreSQL Serverless v2 writer with explicitly bounded capacity and no extra readers or unsupported options.
- Bind assumptions and pricing lines into canonical evidence, approval validation, and safe summaries while retaining old manifest compatibility.
- Add positive and fail-closed tests, update the evidence matrix/backlog, and record all validation.

## Acceptance criteria

- [ ] Only the explicitly supported Aurora PostgreSQL Serverless v2 configuration receives a price.
- [ ] Every billable capacity, storage, I/O, and backup cost is modeled with a timestamped regional AWS Price List product and explicit quantity range.
- [ ] Unknown/missing assumptions and unsupported configuration fail closed before price approval.
- [ ] Pricing assumptions are trusted persisted context, digest-bound, canonical, and not model-authored rates.
- [ ] Legacy pricing evidence manifests remain readable and current evidence remains approval-verifiable.
- [ ] Focused tests and required repository checks pass.
- [ ] Documentation conventions and `git diff --check` pass.
- [ ] No AWS resource, Terraform state, feature gate, customer credential, or workload is changed.

## Acceptance status

Bootstrap ticket only; implementation and validation have not started.

## Tests / validation performed

No tests yet. This bootstrap commit contains only this ticket.

## Evidence files produced

No customer workload is run by this source-only pricing change; no `docs/test/test424.md` is required.

## Boundaries

- Do not run Terraform or mutate AWS.
- Do not change hosted feature gates or deploy the control plane.
- Do not claim pricing support for Aurora unless every material modeled cost is included and its limits remain explicit.
- Preserve `--only-show-errors`, `.venv-pr399/`, and the retained clean-room evidence.

## Follow-up work

After merge and a separately authorized hosted release, exercise an authenticated customer plan with this exact Aurora shape and real regional usage assumptions. Hosted apply, health, recovery, and cleanup remain separate acceptance gates.
