# test410 — PR #410 SQS pricing evidence

Date: 2026-11-14
Execution type: Local deterministic unit and integration tests
Customer repository: None; no customer workload was created
Commit: `ead02fbc8f84c2783edc1a637431040e051a2241`
AWS account: None; catalog evidence is read-only price-list data
AWS region: `us-east-1` for product match; local tests do not access AWS

## Scope and execution boundary

This is local deterministic verification of SQS request pricing and customer
revision binding. No customer workload was generated or applied, no Terraform
plan was run, and no AWS resources were created, changed, or deleted. The
hosted backend remains PR #405; PR #410 has not been deployed. The latest
merged backend source is PR #409 at `024a7b1fe4ea53f8fadcc921575e9716ab92da94`.

## Resources created

No customer or AWS workload resources. `uv` created the local `.venv` used for
verification; it is retained in the PR worktree.

## Price catalog evidence

Read-only AWS Price List Query API results were filtered to `AWSQueueService`,
`productFamily=API Request`, exact `queueType`, and `regionCode=us-east-1`.
The Standard product was SKU `8RN6B8U4MERHRXP3`, published 2026-11-11, with
published rates of `$0.00000040`, `$0.00000030`, and `$0.00000024` per billed
request unit. The FIFO product was SKU `624ZQ7K46KHFAD9Y`, published
2026-11-11, with rates of `$0.00000050`, `$0.00000040`, and `$0.00000035`.
The query did not inspect customer billing or allowance consumption.

AWS's [SQS pricing page](https://aws.amazon.com/sqs/pricing/) describes a
one-million monthly free-request allowance, 64 KB payload billing units,
additional Fair Queue request rates, separate KMS charges, and cross-region
or internet data transfer charges. The estimate accepts billed request units
after payload chunking, retries, and polling; it applies the allowance once
to the lower estimate, FIFO first, and does not apply it to the budget ceiling.
Non-zero Fair Queue surcharges and cross-region or internet transfer ranges,
and customer-managed KMS, block this estimate. Declared zero Fair Queue and
transfer ranges are customer assumptions, not independently verified traffic
observations. A complete application estimate still requires priced database,
compute, networking, and all other material resources.

## Commands executed

Commands run from the backend repository root:

```text
uv run --extra dev python -m pytest tests/test_sqs_plan_pricing.py tests/test_pricing_usage_assumptions.py tests/test_generated_plan_pricing.py tests/test_infrastructure_plan_lifecycle.py -q
uv run ruff check apps/api/src/davdeploy/domain.py apps/api/src/davdeploy/service.py apps/api/src/davdeploy/generated_plan_pricing.py tests/test_sqs_plan_pricing.py tests/test_pricing_usage_assumptions.py tests/test_generated_plan_pricing.py tests/test_infrastructure_plan_lifecycle.py
make verify PYTHON=python3.14
python3.14 scripts/check_doc_conventions.py
git diff --check
```

Results: focused lifecycle/pricing checks passed; Ruff passed; `make verify`
passed 1,215 tests, configuration checks, OpenAPI snapshot validation, and
Docker Compose configuration; documentation conventions and whitespace checks
passed. One pre-existing Starlette/httpx deprecation warning was emitted by the
test suite. The merge gate is the required GitHub Actions checks on PR #410.

## Observed result

Local deterministic checks passed. The pricing evidence remains an estimate
based on stated usage, not an AWS bill or measured customer traffic. The tests
cover exact regional Standard/FIFO catalog filters and provenance, bounded
request, Fair Queue, and transfer assumptions, immutable revision persistence
and clearing, unknown or mismatched queue type, customer-managed KMS, missing
or ambiguous prices, the single lower-estimate allowance, high-cost budget
checks, multiple queues sharing one proposal-wide cost, approval binding, and
cost-quantity tampering. They use simulated
catalog responses and do not constitute an AWS workload test.

## Teardown

No AWS resources were created, so no AWS teardown was needed. Retain this local
worktree and its `.venv` under the current local-file retention instructions.

## Final boundary

This PR improves source-only pricing evidence. It does not deploy the code,
enable customer apply, or demonstrate a Nova-generated customer application.
