# ticket318: Bind trustworthy price and budget evidence to Nova plan approval

PR: #318 (draft)  
Branch: `feat/nova-plan-pricing-evidence`

## Goal

Calculate bounded monthly cost evidence from the actual Nova-generated Terraform plan using a deterministic resource-price mapping and AWS Price List data. Bind the evidence to the immutable plan manifest so approval cannot outlive, omit, or alter the estimate. Unknown usage, unpriced material resources, ambiguous price results, and a cost range over the stated monthly budget must remain ineligible for approval.

## Current repo state

- PR #315 adds fail-closed checks for critical unknown values in generated Terraform plans.
- `GeneratedTerraformPlanRunner` runs a fixed pinned Terraform plan and keeps the parsed `terraform show -json` document inside the runner. Its public result currently contains only a safe action summary and digests.
- `GeneratedPlanArtifact` stores an immutable manifest and policy evidence. The manifest binds proposal/configuration/provider/saved-plan/policy digests, but not pricing or budget evidence.
- `WorkloadRequirements` has an optional USD monthly budget; `CostAssumption` fields supplied in a proposal are descriptive model text and are not a verified price source.
- Existing `FixturePricingCatalog` provides explicitly labeled profile-level fixture ranges. `StsAwsDiscovery._pricing_evidence` performs one sample Price List lookup without parsing a rate and a separate Cost Explorer historical spend query. Neither is used as actual-plan cost evidence.

## Research and references

- AWS Price List Query API: https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/
- Query workflow and filter behavior: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-price-list-query-api.html
- Price list informational-use and Savings Plan limitations: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html
- AWS Pricing Calculator workload estimates count only usage explicitly supplied: https://docs.aws.amazon.com/cost-management/latest/userguide/pc-workload-estimate.html
- AWS Price List calls are free, per AWS's announcement: https://aws.amazon.com/blogs/aws-cloud-financial-management/aws-price-list-gets-a-natural-language-upgrade-introducing-the-aws-pricing-mcp-server/
- Cost Explorer API pricing: https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/

The pricing API endpoint region is separate from the product's AWS region. Price selection must verify the returned product region and attributes. Public list rates are estimates, not actual billing, do not include all discounts/commitments, and cannot infer unprovided workload usage.

## Work planned

- Add an injectable Price List client and typed cost result/evidence in DavDeploy-owned code.
- Read region, currency, and any monthly ceiling from the integrity-checked persisted customer revision; never treat a Nova-declared amount as authoritative. If Nova declares a conflicting budget, fail closed.
- Add an explicit allowlist of priceable plan resource/usage combinations and exact regional/product filters.
- Parse unique On-Demand USD price dimensions and calculate estimates only from known bounded quantities or trusted usage assumptions.
- Treat unpriced material resources, missing variable-usage assumptions, ambiguous/missing products, stale or failed pricing lookup, and unsupported currencies as incomplete and not approval-eligible. Never treat a missing rate as zero.
- Compare the estimate with the persisted customer budget when present. Label it a post-apply steady-state public On-Demand price-list estimate, not a bill forecast or spend cap; record that transition-period charges are excluded.
- Require every planned AWS resource to have a matching change record or an explicit delete/replacement treatment. Missing final-state evidence must block review.
- Bind cost evidence and policy outcome into the immutable plan manifest/database record and revalidate on approval.
- Add offline Price List response fixtures; do not call AWS from tests or add customer IAM permissions.

## Acceptance criteria

- [ ] Price queries and attribute filters are selected only by deterministic DavDeploy code; Nova cannot supply authoritative SKUs, rates, usage quantities, or price filters.
- [ ] The estimate is bound to the exact actual plan, trusted region, currency, rate source/time, and explicit usage assumptions.
- [ ] A missing, ambiguous, failed, stale, unsupported, or variable/unassumed material price is visibly incomplete and cannot be approved.
- [ ] When a monthly budget is present, the conservative estimate is compared with it; an over-budget plan cannot be approved.
- [ ] Cost evidence is included in the immutable manifest digest and checked against stored values at approval time.
- [ ] Only public AWS Price List API is used; no Cost Explorer, paid pricing API, customer permission change, or AWS workload mutation is introduced.
- [ ] Focused local tests cover price response parsing, regional selection, quantities/units, cache behavior, ambiguity, failures, unknown usage, budget boundaries, and approval tampering.
- [ ] Required CI passes and ticket evidence is current.

## Validation performed

The isolated evaluator and offline fixture tests are in progress. `python -m pytest -q tests/test_generated_plan_pricing.py` passes locally with 38 cases; Ruff lint/format and `git diff --check` pass for those files. No AWS Price List call, customer cloud call, Cost Explorer request, or cloud mutation has been made. Runner, immutable-manifest, and approval-boundary integration are pending the in-progress ownership runner interface in PR #317.

## Evidence files

No customer workload run is in scope. No `docs/test/test318.md` is required unless this PR later runs a customer workload test.

## Boundaries

- This package estimates post-apply steady-state public On-Demand list pricing for resources and usage it can explicitly price. Transition-period charges are excluded. It is not an invoice, complete bill forecast, discount-aware forecast, Free Tier calculation, Savings Plan estimate, or hard spend cap.
- Nova-authored prices and budget requirements are not trusted. The persisted customer budget is authoritative; a conflicting Nova-declared budget is not reviewable.
- It does not change customer IAM, deploy infrastructure, use Cost Explorer, or make an unpriced plan approvable by default.
- Existing ownership-tag behavior is out of scope. Any additive runner-interface change will carry only cost evidence and must avoid ownership-policy behavior.

## Follow-up

Expand the deterministic priced-resource catalogue with cost-driving usage definitions and regional validation. Keep any material resource without supported price/usage mapping not approval-eligible until its calculation and tests are added.
