# test414 — bounded DynamoDB on-demand plan pricing

Date: 2026-11-16
Execution type: Local implementation/tests and read-only AWS Price List queries. No AWS workload execution.
Customer repository: `Bepoadewale/davdeploy`
AWS account: `654654474502` (read-only catalog access only)
AWS region: `us-east-1`
Branch: `feat/nova-dynamodb-plan-pricing-414`
Commit: implementation commit to be recorded after final local checks.
Starting source: PR #413 merge `de873ef9e22a96ec38aa4650741b42ff73f053f1`
PR branch base: `3368a432823beed62498935b0204913fbe740d51`
Deployed backend: PR #411; PR #414 is not merged or deployed.

## Read-only AWS Price List evidence

AWS Price List `GetProducts` requests used exact service, product-family,
region, group/volume-type and unit filters. The returned product SKUs and
prices were:

- DynamoDB on-demand reads, `DDB-ReadUnits`, `ReadRequestUnits`: SKU
  `4W4ZMC46EHE8XTTZ`, `$0.0000001250` per request unit.
- DynamoDB on-demand writes, `DDB-WriteUnits`, `WriteRequestUnits`: SKU
  `FGXVD96DKJMUASY3`, `$0.0000006250` per request unit.
- DynamoDB Standard indexed table storage, `GB-Mo`: SKU `F3E2EDSYC6ZNW7XP`,
  published tiers include `$0.25/GB-month` above the first 25 GB. The estimate
  uses the highest published rate for all quantities and does not assume the
  free allowance.
- DynamoDB PITR backup storage, `GB-Mo`: SKU `TFXQN9PEG62G7A67`,
  `$0.20/GB-month`.

AWS documents on-demand read/write units and table storage in its
[DynamoDB pricing page](https://aws.amazon.com/dynamodb/pricing/). It states
that PITR is billed based on table size, including table data and local
secondary indexes, in the [PITR guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery_Howitworks.html).
The estimate records product SKU, digest, publication/effective timestamps,
and source price for every modeled line. Prices can change; the timestamped
catalog result is an estimate input, not a bill or billing cap.

## Validation

- `./.venv/bin/python -m pytest -q tests/test_dynamodb_plan_pricing.py tests/test_pricing_usage_assumptions.py tests/test_sqs_plan_pricing.py` — 31 passed.
- `./.venv/bin/python -m pytest -q tests/test_generated_plan_pricing.py tests/test_dynamodb_plan_pricing.py tests/test_pricing_usage_assumptions.py tests/test_sqs_plan_pricing.py` — 120 passed.
- `make verify` — passed: 1,252 tests, Ruff, Actions configuration, OpenAPI snapshot, and Docker Compose configuration. One existing Starlette/httpx deprecation warning was emitted.
- `python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Required GitHub CI — pending.

## Commands executed

- AWS Price List `GetProducts` with exact `AmazonDynamoDB`, regional,
  family, group or volume-type and unit filters — read-only product lookups;
  no AWS workload API was called.
- The focused pytest commands and `make verify` listed above.
- `python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.

## Observed result

The source adds digest-bound, per-table ranges for billed read request units,
write request units, table storage, and PITR storage. It estimates only
single-region Standard `PAY_PER_REQUEST` tables without indexes, replicas,
streams, or customer-managed KMS keys. It uses the exact regional Price List
products, conservative published rates, and cent rounding. Missing or stale
assumptions, unknown cost-driving values, unsupported settings, mismatched
tables, and unavailable or ambiguous prices keep approval blocked. Pricing
evidence manifest version 7 retains parsing support for older versions.

This is a partial plan estimate. Provisioned capacity, Standard-IA, indexes,
replicas, streams, exports, on-demand backups, customer-managed key costs,
cross-region transfer, and other unsupported charges remain unpriced and
approval-blocking. No Nova customer plan was generated, applied, or certified.

## Resources created

No AWS workload resources were created, changed, applied, or destroyed. The
AWS calls were read-only catalog queries; no teardown was required. The PR
does not enable hosted planning or apply and does not change runtime flags.

## Teardown

No AWS resources were created, so no cloud teardown was required.

## Final boundary

This is source and catalog evidence only. No customer Nova plan, applied
workload, application health check, lifecycle, or certification is claimed.
