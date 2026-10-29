# test203 - Targeted API rate limits and security alerts

## Commands executed

```sh
uv run pytest -q tests/test_operational_surfaces.py tests/test_serverless_runtime.py
terraform -chdir=infrastructure/terraform/serverless-control-plane fmt -check
terraform -chdir=infrastructure/terraform/serverless-control-plane init -backend=false
terraform -chdir=infrastructure/terraform/serverless-control-plane validate
make verify
```

## Result

Focused tests passed: 30 tests. Terraform formatting, offline initialization, and validation passed.
The complete local verification passed: Ruff, 307 tests, OpenAPI snapshot, and Compose configuration.

`make local-proof` was also started. It refreshed the local package but stopped before service
startup because Docker Desktop was not running, so no Compose smoke, customer-plan, seed, or trace
evidence was produced. The required clean-room cycle remains pending because the repository's
clean target removes Docker volumes, `.venv`, and `.local`, and that deletion requires separate
user approval under the machine-wide safety rules.

## Execution boundary

Local tests and Terraform static validation only. No AWS plan or apply, Cognito change, customer
cloud action, email, queue replay, or customer data access is authorised by this evidence.

## Known limitations

API Gateway throttling is distributed and authoritative. The Lambda fallback limiter is per runtime
instance and intentionally defense in depth, not the primary distributed limiter. Cognito metrics
are aggregated and cannot identify a user or expose authentication content.
