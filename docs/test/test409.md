# test409 — revision-bound S3 price evidence

Date: 2026-11-14
Execution type: Local implementation/tests, read-only AWS Price List queries, and GitHub CI. No AWS workload execution.
Customer repository: `Bepoadewale/davdeploy`
Commit: `302aafbbbfec6e5f4e04b9c4e5fe9369e413e677`
AWS account: Not used
AWS region: Not used
Branch: `feat/nova-s3-pricing-409`
Starting source: PR #408 merge `aa8d3d0ee1329da14f5fea32053e8a0970049bee`
Deployed backend: PR #405; this branch is not deployed.
AWS workload account/region: Not used / not used

## Read-only price catalog evidence

Queries used the authenticated `ai-platform-pilot-key` profile only for AWS Pricing read APIs. They created no resources and did not print credentials. The service endpoint was `us-east-1`; product filters bound the returned offer to the target AWS region and usage family.

- `AmazonS3`, product family `Storage`, `regionCode=us-east-1`, `storageClass=General Purpose`, `volumeType=Standard`: SKU `WP9ANXZGBYYSGJEA`, published 2026-11-09, effective 2026-10-01. Rates were $0.023, $0.022, and $0.021 per GB-month across the catalog tiers.
- `AmazonS3`, product family `API Request`, `regionCode=us-east-1`, `group=S3-API-Tier1`: SKU `E9YHNFENF4XQBZR6`, $0.000005 per request ($0.005 per 1,000).
- `AmazonS3`, product family `API Request`, `regionCode=us-east-1`, `group=S3-API-Tier2`: SKU `ZWQ6Q48CRJXX4FXE`, $0.0000004 per request ($0.004 per 10,000).
- `AWSDataTransfer`, product family `Data Transfer`, `fromRegionCode=us-east-1`, `toLocation=External`, `transferType=AWS Outbound`: SKU `HQEH3ZWJVT46JHRG`, $0.09/GB first tier, published 2026-11-11, effective 2026-11-01. The [AWS S3 pricing page](https://aws.amazon.com/s3/pricing/) documents the shared 100 GB/month internet transfer allowance, declining rate tiers down to $0.05/GB, and a separate quote requirement above 500 TB/month.

The implementation records the exact matching Price List product digest, SKU, publication time, and effective time. Low estimates use the lowest published storage/egress unit rates and the documented shared transfer allowance; high estimates use the highest regional catalog rates without assuming discounts or free allowance. Internet egress assumptions above 500 TB/month block approval.

## Commands executed

- `uv run python -m pytest -q tests/test_generated_plan_pricing.py tests/test_pricing_usage_assumptions.py tests/test_generated_plan_review.py tests/test_nova_plan_dispatch.py tests/test_nova_plan_runs.py tests/test_nova_plan_codebuild.py tests/test_generated_plan_artifacts.py` — 220 passed, one existing Starlette/httpx deprecation warning.
- `uv run python -m ruff check apps/api/src/davdeploy/generated_plan_pricing.py apps/api/src/davdeploy/nova_plan_codebuild.py apps/api/src/davdeploy/nova_plan_dispatch.py apps/api/src/davdeploy/generated_plan_artifacts.py apps/api/src/davdeploy/service.py tests/test_generated_plan_pricing.py tests/test_nova_plan_dispatch.py tests/test_nova_plan_runs.py tests/test_nova_plan_codebuild.py` — passed.
- `make verify PYTHON=python3.14` — passed: 1,200 tests, Ruff, action configuration, OpenAPI snapshot, and Docker Compose configuration (one existing Starlette/httpx deprecation warning).
- `python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.
- GitHub Actions run [43594664860](https://github.com/Bepoadewale/davdeploy/actions/runs/43594664860) on PR head `d009167` — all seven jobs passed. `local-e2e` ran the fresh-runner lifecycle; `cloud-contracts` validated Terraform and Kubernetes contracts.

## Observed result

Pricing now covers explicitly assumed S3 Standard storage, PUT/COPY/POST/LIST requests, GET requests, and internet egress for proposal-wide aggregate use across plain S3 buckets. The assumptions come only from the digest-checked persisted revision. The output binds low/high costs and rates to exact plan/context digests and catalog provenance, uses the high estimate for the budget gate, and increments the pricing evidence, saved-plan manifest, and worker result contract versions.

Missing assumptions, multiple/invalid resource transitions, Object Lock, unsupported egress volume, ambiguous/missing catalog products, and any other material unpriced resource remain approval blockers. Object versioning, customer-managed keys, non-Standard storage, replication, retrieval, lifecycle, accelerated/cross-region transfer, and other unmodeled charges are not treated as free.

## Resources created

No AWS workload resources were created, changed, applied, or destroyed.

## Teardown

No cloud resources were created, so no teardown was required.

## Final boundary
 There is no customer application behavior, runtime usage, billing, teardown, or absence claim. This is source and pricing-catalog evidence only; PR #409 is not deployed and does not establish customer Nova plan or apply readiness.
