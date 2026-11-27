# test555 — deterministic Nova resource ID normalization

Date: 2026-11-27
Execution type: Local contract/generation tests planned; hosted run pending
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance case)
Commit: `2d79b15f03a922289667e1f5bdea60763ac92f25`; PR implementation pending
AWS account: `654654474502` (control-plane release only)
AWS region: `us-east-1`

## Resources created

No customer AWS workload resources were created. The failed v18 run produced no CodeBuild build or saved plan.

## Commands executed

- Authenticated read-only `GET /api/v1/generated-plan-runs/9cd5f381-7300-431d-9b13-e3c0b337a67d`: `FAILED`, no artifact, prompt v18, two attempts/one repair, safe `string_pattern_mismatch` at `resources[*].resource_id`.
- No raw proposal, identifier value, Terraform plan, or customer workload was retrieved or created.
- Focused tests passed (60); full `make verify` passed 2,072 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose checks. Documentation conventions and PR CI remain pending.

## Observed result

The v18 hosted retry failed before CodeBuild after bounded repair. Fixed guidance improved the diagnostic but did not correct the generated ID. PR #555 will add deterministic normalization while retaining strict validation and rejecting ambiguity.

## Teardown

No workload resources were created, so no teardown was needed. The terminal failed run remains as evidence.

## Final boundary

This evidence does not prove an inspectable hosted plan or the composed API/storage/database/async milestone. No customer review approval or workload apply occurred.
