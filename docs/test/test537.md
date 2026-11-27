# test537 — Nova Terraform resource-name prompt constraint

Date: 2026-11-27
Execution type: Hosted plan-only retry diagnosis and focused local tests
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance input)
Commit: `95ce2aa76cbefedf94b5949866f7d29ecf4cd995` (diagnostics deployment)
AWS account: `654654474502`
AWS region: `us-east-1`

## Resources created

No AWS workload resources were created. The retry failed during Nova proposal
validation before CodeBuild. No saved plan artifact was produced.

## Commands executed

- Authenticated CLI GET for generated-plan run status — confirmed safe bounded
  failure diagnostics; raw model output was not accessed.
- `uv run --project . --extra dev pytest -q tests/test_terraform_generation.py tests/test_nova_plan_runs.py tests/test_customer_plan_review.py` — 97 passed.
- Ruff — passed for the five changed Python files.
- Documentation convention checks and `git diff --check` — passed.

## Observed result

The submitted revision's existing run
`0b1e4807-7532-45df-ad99-8edde41a82f4` was confirmed failed and retried once
through the authenticated API. It returned `NOVA_GENERATION_FAILED` with safe
diagnostics: model `us.amazon.nova-2-lite-v1:0`, prompt v4, two attempts, one
repair, eight `string_pattern_mismatch` errors on `resources[*].name`, 11,169
input tokens, 3,070 output tokens, and 12,123 ms latency. Estimated model cost
was not returned. The proposal content was not read or retained.

No CodeBuild build, plan artifact, or AWS workload was created.

## Teardown

No workload resources were created; no teardown was required.

## Final boundary

A corrected prompt alone does not prove Nova can generate a valid plan. Repeat
the hosted plan-only request after deployment and record a valid artifact or a
new safe diagnostic. Do not approve or apply this proposal.
