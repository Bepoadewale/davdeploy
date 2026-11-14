# PR #409 — Price revision-bound S3 usage assumptions

## Goal

Use current regional AWS Price List data to price supported Amazon S3 Standard storage, request, and internet egress usage in Nova generated-plan evidence. Bind every estimate to the exact persisted usage-assumption revision, proposal, plan, region, and catalog evidence. Keep approval blocked whenever a material S3 charge dimension, usage assumption, or catalog rate cannot be established.

## Current repository state

This branch starts from backend main PR #408 (`aa8d3d0`), which adds typed, immutable-revision-bound S3 usage assumptions and includes them in pricing context and result contract v4. PR #407 prices explicitly sized EBS gp3 only. Unsupported material plan costs block approval. The hosted backend release remains PR #405; no Nova customer workload has been applied.

## Research and references

- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/): storage, requests/retrieval, data transfer, and other charge dimensions depend on usage and storage class.
- [AWS Price List Query API — GetProducts](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html): regional product catalog filters and offer data.
- [AWS Price List Query API — attribute discovery](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_DescribeServices.html): service attributes used to constrain catalog lookup.
- Read-only AWS Pricing API queries in `us-east-1` identified S3 Standard storage and request product families and regional usage types. Exact matched rates and product identities will be recorded after implementation verification.

## Work

- Extend the trusted regional catalog lookup to resolve exact, current S3 Standard storage, PUT/COPY/POST/LIST request, GET request, and internet-egress rates from narrowly filtered AWS Price List products.
- Calculate conservative low/high monthly costs from persisted bounded usage ranges, with explicit units, rounding, catalog SKU/product digest, publication/effective times, and usage assumptions on each evidence line.
- Reject ambiguous, missing, malformed, stale, unsupported, or unpriced material rates and charge dimensions; do not infer unmodeled retrieval, lifecycle, replication, encryption-key, acceleration, or transfer charges as free.
- Version and validate any changed evidence/manifest contract, preserve digest and approval binding, and keep all generated values redacted from unsafe logs.
- Add deterministic tests for rate selection, ranges, rounding, catalog ambiguity/unavailability, unsupported dimensions, stale/tampered evidence, and approval eligibility.

## Acceptance criteria

- [ ] Exact regional rates are obtained only from trusted AWS Price List results; Nova/customer values cannot provide prices.
- [ ] Supported S3 monthly cost ranges are calculated from immutable persisted assumptions and recorded with source provenance and digests.
- [ ] Missing assumptions or unsupported S3 charge dimensions yield explicit incomplete evidence and prevent approval.
- [ ] Tampering with assumptions, rate identity, product digest, evidence, proposal, or plan is rejected before approval.
- [ ] Focused tests, full `make verify`, documentation conventions, and required GitHub CI pass.
- [ ] Implementation status and this ticket accurately distinguish source status from deployed status; no customer AWS workload is claimed.

## Validation and evidence

- Initial state: planned; no code or customer workload test has been performed.
- Evidence file: `docs/test/test409.md` will record validation and explicitly state whether AWS workload execution occurred.

## Boundaries and follow-up

This PR does not apply infrastructure or make S3 plans eligible where any charge is not modeled. It does not claim a full S3 bill estimate, a hard spending cap, or hosted Nova deployment readiness. S3 Glacier classes, intelligent tiering, lifecycle transitions, replication, retrieval, KMS request charges, acceleration, and non-internet transfer remain unsupported unless separately modeled and validated.
