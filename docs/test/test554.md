# test554 — safe Nova graph validation feedback

Date: 2026-11-27
Execution type: Focused tests and authenticated hosted status read; no AWS workload
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance case)
Commit: source `38849b326cb3ac6db5a8d96aad4cbcfce66a6fc2`; PR implementation pending
AWS account: `654654474502` (read-only identity/status context)
AWS region: `us-east-1`

## Resources created

No AWS workload resources were created or changed. The existing control plane was only queried for the safe status of the failed plan-only request.

## Commands executed

- Authenticated `GET /api/v1/generated-plan-runs/e2395afb-6017-4ceb-9be1-6fdd5661e3c5` returned `FAILED`, `NOVA_GENERATION_FAILED`, no artifact, prompt v17, and one root `value_error` diagnostic. No raw proposal was fetched.
- Focused tests: `pytest -q tests/test_terraform_generation.py tests/test_generated_deployment_contract.py` — 108 passed.
- Ruff and `git diff --check` passed. `make verify` passed (2,064 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose); documentation conventions and diff checks passed. PR CI runs `46031809126` and `46032341067` passed all seven checks; `46032341067` includes the implementation and initial evidence update. Hosted v18 generation remains pending.

## Observed result

The retry is terminal and failed before CodeBuild. PR #554 adds fixed mappings for known proposal graph and lifecycle assertion causes, plus fixed opaque fallback for unknown causes. No Terraform plan or customer workload exists.

## Teardown

No workload resources were created, so no teardown was required. The failed run remains as audit evidence.

## Final boundary

This is diagnostic and local implementation evidence only. The first hosted-plan gate remains unmet. No customer review was approved, and no workload apply or destroy occurred. Any later artifact must prove supported API, private storage, database, async work, current regional prices, and exact plan policy before it can count toward the gate.
