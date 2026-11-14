# ticket408 — explicit S3 cost usage assumptions

PR: draft
Branch: `feat/nova-pricing-usage-408`

## Problem / goal

The merged Nova pricing evaluator only prices explicitly sized EBS gp3
volumes. S3 is necessary for the first composed application and its storage
and request costs depend on customer usage. Add a typed, bounded, revision-bound
usage contract and deterministic S3 Standard storage/request pricing. Costs
that depend on unsupported dimensions remain visible and block approval.

## Current repo state

Backend `main` is `aebc5f6c2d35826f864ae7eff15c475db6fcc0f9` (PR #407). The
control-plane release is still PR #405; PR #407 is merged source, not deployed.
It prices EBS gp3 only; other material costs remain approval blockers. PR #399
is an open draft for a disabled exact-plan apply boundary and must stay gated
until price coverage is complete. No Nova customer plan or workload has been
executed.

## Research / references used

- Local source: `generated_plan_pricing.py` binds estimates to the immutable plan and persisted revision digest; `domain.py` already captures average/peak requests and budget, while user-edited revision constraints create new revisions.
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/) describes distinct storage, request/retrieval, data transfer, management, replication, and transform charges; charges vary by storage class and operation.
- [AWS Price List Query API product lookup](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-price-list-query-api.html) documents product attribute discovery and filters; all filter terms must match.
- [AWS GetProducts API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html) returns products matching filter criteria with SKU-level product and price metadata.

## Work planned for the PR

- Add a strict typed usage-assumption object to the persisted workload revision for S3 Standard storage and monthly PUT/LIST and GET requests. Require explicit low/high quantities and bounded units; no model-authored prices or arbitrary fields.
- Validate assumptions at revision update and at planner input from the digest-checked persisted revision. Bind them into the pricing context, exact plan evidence, and plan review.
- Query exact regional AWS Price List products for storage and request dimensions. Require unambiguous USD On-Demand rates with SKU and effective/publication/retrieval provenance; never fall back to hard-coded prices.
- Price only those explicitly declared dimensions. Missing assumptions, other S3 storage classes/features, data transfer, minimum-duration effects, and all unsupported material resources remain approval blockers.
- Add negative tests for malformed, excessive, missing, stale, altered, mismatched, ambiguous, or unavailable assumptions/rates.
- Update current source/deployment status and keep PR #399's apply path gated.

## Acceptance criteria

- [ ] S3 assumptions are typed, bounded, customer-visible, stored in a new immutable revision, and digest-bound to the plan price context.
- [ ] S3 Standard storage, PUT/LIST, and GET estimates use exact regional AWS Price List data and explicit monthly ranges; missing material dimensions remain incomplete.
- [ ] Review shows input ranges, pricing units, rate provenance/timestamps, calculated range, and exclusions without exposing raw plan data.
- [ ] Approval revalidates the exact persisted usage-context digest and evidence freshness.
- [ ] Negative cases fail closed; no unpriced material S3 feature appears complete.
- [ ] Focused tests, full verification, documentation conventions, clean-runner lifecycle, Terraform validation, and required CI pass; no AWS workload resources are created or changed.

## Acceptance status

Not started. Draft bootstrap only. No implementation, live catalog request, customer plan, or workload mutation has occurred.

## Tests / validation performed

Draft creation and source/deployment reconciliation only. Focused and full validation will be added before review.

## Evidence files produced

- `docs/tickets/ticket408.md`
- `docs/test/test408.md` will record final local and CI validation.

## Boundaries

No AWS workload mutation or apply path is in scope. AWS prices are public On-Demand list prices, not a bill, discount-aware forecast, or hard spend cap. No customer plan becomes approval-eligible merely because these S3 dimensions are priced.

## Follow-up work

Price the first hosted-milestone database and asynchronous-work dimensions, then validate realistic composed-plan completeness before connecting exact-plan approval/apply.
