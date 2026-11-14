# ticket410 — Price revision-bound SQS usage

PR: #410
Branch: `feat/nova-sqs-pricing-410`

## Problem / goal

Price supported Amazon SQS Standard and FIFO queues in generated Terraform plan evidence. Bind monthly billed request-unit, Fair Queue, and transfer assumptions to the exact persisted plan revision, region, plan, and regional AWS product catalog evidence. Keep approval blocked when queue configuration, usage, or any material price dimension is unsupported.

## Current repo state

Backend source main is PR #409 merge `024a7b1fe4ea53f8fadcc921575e9716ab92da94`. PR #407 prices EBS gp3; PR #408 adds immutable S3 usage assumptions; PR #409 adds regional S3 Standard and internet egress pricing. All other material plan resources remain approval blockers. The deployed control plane is still PR #405. PR #399 remains a draft and the customer apply boundary is not enabled. No Nova customer workload has been applied.

## Research / references used

- [Amazon SQS pricing](https://aws.amazon.com/sqs/pricing/): requests are priced by queue type and usage volume; AWS documents the monthly free request allowance and billing units.
- [Amazon SQS pricing metering details](https://aws.amazon.com/sqs/pricing/): each API action is a request; payloads are billed in 64 KB chunks; Fair Queue requests can incur an additional rate; cross-region and internet transfer use AWS Data Transfer rates; customer-managed KMS use incurs separate KMS calls.
- [AWS Price List Query API — GetProducts](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html): regional product and price lookup.
- Read-only AWS Price List queries in `us-east-1` found SQS Standard SKU `8RN6B8U4MERHRXP3` at $0.00000040/request for the first published tier, then $0.00000030 and $0.00000024; FIFO SKU `624ZQ7K46KHFAD9Y` at $0.00000050, $0.00000040, and $0.00000035. Both products were published 2026-11-11.
- The cost context treats customer inputs as billed request units after 64 KB payload chunking, retries, and polling. It applies the one-million monthly allowance once to the lower estimate, FIFO first, and excludes that shared account-wide allowance from the budget ceiling.

## Work planned for the PR

- Add strict bounded monthly billed-request-unit ranges for Standard and FIFO queues, Fair Queue requests, and transfer ranges to the customer usage-assumption contract; preserve immutable revision storage and include all dimensions in trusted pricing context digests.
- Match only the exact regional Standard/FIFO AWS Price List products and validate all rate units, tier coverage, timestamps, SKUs, and product digests.
- Price proposal-wide usage for planned queues, using the highest published rate and no free allowance for budget approval; use documented lowest tier and the shared free allowance only for the lower estimate.
- Require known queue type and region; block customer-managed KMS, unknown billable configuration, missing assumptions, missing/ambiguous prices, non-zero unpriced Fair Queue/transfer assumptions, and unsupported resource changes.
- Extend versioned plan pricing evidence and result/manifest contracts; recheck the exact assumption quantities and costs at approval.
- Add deterministic positive, negative, range, rounding, catalog, tampering, and stale-evidence tests.

## Acceptance criteria

- [x] Queue type and region are derived from the validated actual plan; Nova cannot supply price values.
- [x] Standard and FIFO usage ranges come only from the digest-checked persisted revision and are bound into plan and approval evidence.
- [x] High and low monthly cost ranges use exact regional price provenance and the known SQS tier/free-allowance rules; the budget gate uses the high estimate.
- [x] Unknown, malformed, unsupported, missing, stale, or tampered queue usage or pricing evidence blocks approval.
- [x] Multiple queues of the same type use proposal-wide usage assumptions once, without duplicating total costs.
- [x] Focused tests, full `make verify`, and documentation conventions pass.
- [ ] Required GitHub CI passes on the corrected sparse-plan head.
- [ ] Repository-required full local clean-room lifecycle passes; not run because its `clean-local` target deletes local `.venv`/`.local` and Compose volumes.
- [x] Source status, deployed status, read-only catalog evidence, and workload boundaries are recorded truthfully.

## Tests / validation performed

- Bootstrap only: no implementation or customer workload test has run.
- Evidence file: `docs/test/test410.md` will record validation and confirm that no workload execution occurred.

## Acceptance status

Implemented and locally verified. A corrective plan-format change is awaiting GitHub CI, and the repository-required local clean-room lifecycle remains outstanding. No SQS customer workload or AWS resource has been created.

## Evidence files produced

- `docs/test/test410.md` records the deterministic pricing and lifecycle checks; no workload run occurred.

## Boundaries

This PR does not apply infrastructure or make a plan approvable when databases, storage, application compute, networking, or any other material cost remains unpriced. Usage assumptions cover billed SQS request units, including retries and 64 KB message-size request units; they are not observed usage or a billing cap. Non-zero cross-region/internet transfer, customer-managed KMS, Fair Queue surcharges, and other unsupported queue behavior block this estimate. Zero transfer/Fair Queue ranges are customer assumptions and are not independently verified. Price-list free usage cannot establish any account's actual allowance consumption.

## Follow-up work

Continue pricing and plan policy for the API application's database, compute, networking, and other material resources; then connect the generic runner to the hosted worker and prove the complete application lifecycle.
