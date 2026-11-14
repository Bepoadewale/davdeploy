# ticket408 — explicit S3 cost usage assumptions

PR: [#408](https://github.com/Bepoadewale/davdeploy/pull/408) (draft)
Branch: `feat/nova-pricing-usage-408`

## Problem / goal

The merged Nova pricing evaluator only prices explicitly sized EBS gp3
volumes. S3 is necessary for the first composed application and its storage,
request, and transfer costs depend on customer usage. Add a typed, bounded,
revision-bound customer usage contract that the next pricing slice can consume.
This PR makes assumptions inspectable and digest-bound; it does not mark S3
costs complete.

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

- Add a strict typed usage-assumption object to user-editable plan constraints for monthly S3 Standard storage, write requests, read requests, and internet egress. Require bounded low/high quantities and units; accept no arbitrary fields.
- Persist assumptions only in a new immutable draft revision. Validate at API input and again when the planner loads the integrity-checked persisted revision.
- Bind the canonical assumptions to trusted pricing context and returned evidence; show them in plan review alongside unresolved cost findings.
- Do not add prices or treat assumptions as approval. S3 and other unpriced material resources remain approval blockers until deterministic regional price mappings cover all applicable charge dimensions.
- Add negative tests for malformed, excessive, missing, altered, cross-revision, and digest-mismatched assumptions.
- Update current source/deployment status and keep PR #399's apply path gated.

## Acceptance criteria

- [x] S3 usage assumptions are typed, bounded, customer-editable, and stored only in a new immutable plan revision.
- [x] Planner input reconstructs assumptions only from the digest-checked persisted revision; canonical assumptions are bound into pricing context/evidence digests.
- [x] Plan review displays the bounded assumptions and continues to show S3 cost as incomplete until its regional rates and all material dimensions are covered.
- [x] Altered, oversized, malformed, missing, or cross-revision assumptions fail closed; old approvals cannot authorize an updated assumption set.
- [x] Focused tests, full verification, documentation conventions, clean-runner lifecycle, Terraform validation, and required CI pass; no AWS workload resources are created or changed.

## Acceptance status

Implementation commit `5cb1108dcd624da021cab9637004eaa458e9ac29` adds the typed usage contract, immutable revision flow, pricing-context/evidence binding, and review display. Focused tests (222), full verification (1,193 tests), OpenAPI snapshot, and local docs conventions pass. GitHub Actions run [43591083601](https://github.com/Bepoadewale/davdeploy/actions/runs/43591083601) passed all seven jobs on PR head `47072d9ecc7e104d912b2f62c803f45ee6d1357f`, including fresh-runner lifecycle, Terraform/Kubernetes contracts, and docs conventions. No live catalog request, customer plan, or workload mutation has occurred.

## Tests / validation performed

Exact commands and results are recorded in `docs/test/test408.md`.

## Evidence files produced

- `docs/tickets/ticket408.md`
- `docs/test/test408.md`

## Boundaries

No AWS workload mutation or apply path is in scope. AWS prices are public On-Demand list prices, not a bill, discount-aware forecast, or hard spend cap. No customer plan becomes approval-eligible merely because these S3 dimensions are priced.

## Follow-up work

Price the first hosted-milestone database and asynchronous-work dimensions, then validate realistic composed-plan completeness before connecting exact-plan approval/apply.
