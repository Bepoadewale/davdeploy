# ticket410 — Price revision-bound SQS usage

PR: #410
Branch: `feat/nova-sqs-pricing-410`

## Problem / goal

Price supported Amazon SQS Standard and FIFO queues in generated Terraform plan evidence. Bind monthly billed request-unit assumptions to the exact persisted plan revision, region, plan, and regional AWS product catalog evidence. Keep approval blocked when queue configuration, usage, or any material price dimension is unsupported.

## Current repo state

Backend source main is PR #409 merge `024a7b1fe4ea53f8fadcc921575e9716ab92da94`. PR #407 prices EBS gp3; PR #408 adds immutable S3 usage assumptions; PR #409 adds regional S3 Standard and internet egress pricing. All other material plan resources remain approval blockers. The deployed control plane is still PR #405. PR #399 remains a draft and the customer apply boundary is not enabled. No Nova customer workload has been applied.

## Research / references used

- [Amazon SQS pricing](https://aws.amazon.com/sqs/pricing/): requests are priced by queue type and usage volume; AWS documents the monthly free request allowance and billing units.
- [AWS Price List Query API — GetProducts](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html): regional product and price lookup.
- Read-only AWS Price List queries in `us-east-1` found SQS Standard SKU `8RN6B8U4MERHRXP3` at $0.00000040/request for the first published tier, then $0.00000030 and $0.00000024; FIFO SKU `624ZQ7K46KHFAD9Y` at $0.00000050, $0.00000040, and $0.00000035. Both products were published 2026-11-11.

## Work planned for the PR

- Add strict bounded monthly billed-request-unit ranges for Standard and FIFO queues to the customer usage-assumption contract; preserve immutable revision storage and include both queue assumptions in trusted pricing context digests.
- Match only the exact regional Standard/FIFO AWS Price List products and validate all rate units, tier coverage, timestamps, SKUs, and product digests.
- Price proposal-wide usage for planned queues, using the highest published rate and no free allowance for budget approval; use documented lowest tier and the shared free allowance only for the lower estimate.
- Require known queue type and region; block customer-managed KMS, unknown billable configuration, missing assumptions, missing/ambiguous prices, unsupported transfer, and unsupported resource changes.
- Extend versioned plan pricing evidence and result/manifest contracts; recheck the exact assumption quantities and costs at approval.
- Add deterministic positive, negative, range, rounding, catalog, tampering, and stale-evidence tests.

## Acceptance criteria

- [ ] Queue type and region are derived from the validated actual plan; Nova cannot supply price values.
- [ ] Standard and FIFO usage ranges come only from the digest-checked persisted revision and are bound into plan and approval evidence.
- [ ] High and low monthly cost ranges use exact regional price provenance and the known SQS tier/free-allowance rules; the budget gate uses the high estimate.
- [ ] Unknown, malformed, unsupported, missing, stale, or tampered queue usage or pricing evidence blocks approval.
- [ ] Multiple queues of the same type use proposal-wide usage assumptions once, without duplicating total costs.
- [ ] Focused tests, full `make verify`, documentation conventions, and required GitHub CI pass.
- [ ] Source status, deployed status, read-only catalog evidence, and workload boundaries are recorded truthfully.

## Tests / validation performed

- Bootstrap only: no implementation or customer workload test has run.
- Evidence file: `docs/test/test410.md` will record validation and confirm that no workload execution occurred.

## Acceptance status

Not started beyond the PR bootstrap. No SQS customer workload or AWS resource has been created.

## Evidence files produced

- `docs/test/test410.md` will be added before implementation review.

## Boundaries

This PR does not apply infrastructure or make a plan approvable when databases, storage, application compute, networking, or any other material cost remains unpriced. Usage assumptions cover billed SQS request units, including retries and 64 KB message-size request units; they are not observed usage or a billing cap. Cross-region and internet data transfer, customer-managed KMS, and unsupported queue behavior remain blocked or separately unpriced.

## Follow-up work

Continue pricing and plan policy for the API application's database, compute, networking, and other material resources; then connect the generic runner to the hosted worker and prove the complete application lifecycle.
