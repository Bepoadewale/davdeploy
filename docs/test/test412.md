# test412

Date: 2026-11-15
Execution type: Local code verification plus read-only AWS public Price List queries; no customer workload execution.
Customer repository: Bepoadewale/davdeploy
Commit: 4252a88171c2478b00ce60ef424969dec5ac1952 (implementation commit; evidence-only follow-up commit follows)
AWS account: Not used for workload access; public Price List API only
AWS region: us-east-1 for catalog lookups

## Resources created

No AWS resources were created. The read-only catalog query made no account mutations.

## Commands executed

- Focused: `PYTHONPATH=apps/api/src .venv/bin/python -m pytest -q tests/test_pricing_usage_assumptions.py tests/test_generated_plan_pricing.py tests/test_infrastructure_plan_lifecycle.py tests/test_sqs_plan_pricing.py` — 122 passed; one upstream Starlette/httpx deprecation warning.
- Full: `make verify` — configuration check passed; Ruff passed; 1,242 tests passed; OpenAPI snapshot matched; `docker compose config --quiet` passed. One upstream Starlette/httpx deprecation warning was reported.
- OpenAPI generation: `make openapi-update` — wrote `contracts/openapi-v1.json`; subsequent `make verify` confirmed the snapshot.
- Documentation: `.venv/bin/python scripts/check_doc_conventions.py` — passed.
- Diff hygiene: `git diff --check` — passed.
- Read-only live catalog check used `AWS_PROFILE=ai-platform-pilot-key` and the public AWS Price List API. In `us-east-1`, x86_64 Lambda request/duration were `$0.0000002000/Request` and `$0.0000166667/GB-second`; arm64 were `$0.0000002000/Request` and `$0.0000133334/GB-second`; HTTP API requests were `$0.0000010000/Request`; Standard CloudWatch log ingestion/storage were `$0.5000000000/GB` and `$0.0300000000/GB-month`; AWS internet egress catalog rate was `$0.0900000000/GB`. The evaluator does not hardcode these regional values. The query created no AWS resources.
- Offline price fixtures are tests only and do not represent an AWS bill.

## Observed result

The typed assumptions persist on a new revision and are included in pricing and approval context digests. The evaluator prices only bounded ZIP Lambda functions and HTTP APIs and blocks unknown or unsupported configurations and unpriced material resources. The estimate excludes Free Tier, account credits, discounts, taxes and unmodeled usage; it is not a spend cap.

## Teardown

Not applicable. No AWS workload resources or local service stack were created. The branch-local Python environment is ignored by Git and retained for verification; it was not removed.

## Final boundary

No Nova-generated AWS workload was applied. No hosted deployment, application health, lifecycle, destroy, or independent absence evidence is claimed. Exact-plan apply remains disabled and unwired.

## Policy limits

- Requires bounded monthly Lambda invocations, average billed duration, internet egress, CloudWatch log ingestion and storage, and HTTP API request and egress assumptions for exact plan resource addresses.
- Prices only x86_64/arm64 ZIP Lambda functions with known memory, default 512 MB ephemeral storage, no VPC attachment, and an explicitly retained Standard CloudWatch log group. SnapStart, reserved concurrency, provisioned concurrency, unbounded log retention, VPC/NAT and unsupported settings fail closed.
- Prices only HTTP protocol API Gateway v2 resources. VPC links, detailed stage metrics, access logs, and unpriced material resources block approval.
- Price tiers use conservative regional Price List matches. Estimates exclude Free Tier, account credits, discounts, tax and unmodeled usage; they are not a spend cap.

## Hosted evidence

- GitHub Actions run `43703297346` on commit `937df00` passed all seven checks: `docs-conventions`, `python`, `secrets`, `policy`, `cloud-contracts`, `supply-chain`, and fresh-runner `local-e2e`.
- Final-head run `43703675890` on commit `5185ef1` passed all seven required checks, including the fresh-runner `local-e2e`.
- These runs verify CI and integration behavior. They are not a Nova workload deployment or lifecycle certification.
