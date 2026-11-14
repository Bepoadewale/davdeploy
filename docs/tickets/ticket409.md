# ticket409 — Price revision-bound S3 usage assumptions

PR: #409
Branch: `feat/nova-s3-pricing-409`

## Problem / goal

Use current regional AWS Price List data to price supported Amazon S3 Standard storage, request, and internet egress usage in Nova generated-plan evidence. Bind every estimate to the exact persisted usage-assumption revision, proposal, plan, region, and catalog evidence. Keep approval blocked whenever a material S3 charge dimension, usage assumption, or catalog rate cannot be established.

## Current repo state

This branch starts from backend main PR #408 (`aa8d3d0`), which adds typed, immutable-revision-bound S3 usage assumptions and includes them in pricing context and result contract v4. PR #407 prices explicitly sized EBS gp3 only. Unsupported material plan costs block approval. The hosted backend release remains PR #405; no Nova customer workload has been applied.

## Research / references used

- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/): storage, requests/retrieval, data transfer, and other charge dimensions depend on usage and storage class.
- [AWS Price List Query API — GetProducts](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html): regional product catalog filters and offer data.
- [AWS Price List Query API — attribute discovery](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_DescribeServices.html): service attributes used to constrain catalog lookup.
- Read-only AWS Pricing API queries in `us-east-1` matched S3 Standard storage SKU `WP9ANXZGBYYSGJEA` (published 2026-11-09, effective 2026-10-01; $0.023/$0.022/$0.021 per GB-month across its tiers), PUT/COPY/POST/LIST SKU `E9YHNFENF4XQBZR6` ($0.000005/request), GET SKU `ZWQ6Q48CRJXX4FXE` ($0.0000004/request), and AWS Data Transfer SKU `HQEH3ZWJVT46JHRG` ($0.09/GB first tier; published 2026-11-11, effective 2026-11-01). The S3 page documents the shared 100 GB monthly allowance and declining egress tiers down to $0.05/GB; transfers above 500 TB/month need a separate quote.

## Work planned for the PR

- Extend the trusted regional catalog lookup to resolve exact, current S3 Standard storage, PUT/COPY/POST/LIST request, GET request, and internet-egress rates from narrowly filtered AWS Price List products.
- Calculate conservative low/high monthly costs from persisted bounded usage ranges, with explicit units, rounding, catalog SKU/product digest, publication/effective times, and usage assumptions on each evidence line.
- Reject ambiguous, missing, malformed, stale, unsupported, or unpriced material rates and charge dimensions; do not infer unmodeled retrieval, lifecycle, replication, encryption-key, acceleration, or transfer charges as free.
- Version and validate any changed evidence/manifest contract, preserve digest and approval binding, and keep all generated values redacted from unsafe logs.
- Add deterministic tests for rate selection, ranges, rounding, catalog ambiguity/unavailability, unsupported dimensions, stale/tampered evidence, and approval eligibility.

## Acceptance criteria

- [x] Regional high rates are selected only from trusted AWS Price List products; the documented AWS pricing page supplies the published low egress tier and allowance. Nova/customer values cannot provide prices.
- [x] Supported S3 monthly cost ranges are calculated from immutable persisted assumptions and recorded with source provenance and digests. High estimates use the highest catalog unit rates without assuming shared discounts; low estimates use the lowest published rate and the documented egress allowance.
- [x] Missing assumptions, unsupported S3 settings, and unsupported egress ranges yield explicit incomplete evidence and prevent approval.
- [x] Existing digest-bound context, rate/product provenance, plan identity, and approval eligibility tests cover changed assumptions, evidence, and plan data; focused PR tests pass.
- [x] Focused tests (220), full `make verify` (1,200 tests), Ruff, OpenAPI, Compose configuration, and documentation conventions pass. GitHub Actions run [43594267261](https://github.com/Bepoadewale/davdeploy/actions/runs/43594267261) passed all seven jobs, including fresh-runner `local-e2e` and Terraform/Kubernetes `cloud-contracts`.
- [x] Status documentation distinguishes source changes from the PR #405 deployed release. No customer AWS workload is claimed.

## Tests / validation performed

- Implementation: in progress; 220 focused tests and 1,200 full verification tests pass, along with Ruff, OpenAPI, Compose, and documentation conventions. The read-only AWS Price List lookup described above used no customer workload resources.
- Evidence file: `docs/test/test409.md` records validation and explicitly states no AWS workload execution occurred.

## Acceptance status

Implementation is in progress. Focused tests, full local verification, Ruff, OpenAPI, Docker Compose validation, and documentation conventions pass; hosted CI passes on PR head `b3afe7f`; the final documentation update still needs its required CI run.

## Evidence files produced

- `docs/test/test409.md`

## Boundaries

This PR does not apply infrastructure or make plans eligible where any material charge is not modeled. Usage ranges apply across proposal S3 Standard buckets. S3 configurations using Object Lock, versioning, customer-managed KMS, non-Standard classes, replication, or other unmodeled charges remain blocked. Egress above 500 TB/month remains blocked because AWS requires a separate quote. It does not claim a full S3 bill estimate, a hard spending cap, or hosted Nova deployment readiness.

## Follow-up work

Price other material resources and complete hosted planning, approval, application, health, recovery, and destroy evidence in later work. S3 Glacier classes, intelligent tiering, lifecycle transitions, replication, retrieval, KMS request charges, acceleration, and non-internet transfer remain unsupported unless separately modeled and validated.
