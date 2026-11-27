# test557 — relational database health target contract

Date: 2026-11-27

Execution type: Hosted plan-only diagnostic and local validation; no customer AWS workload

Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance case)

Commit: `a63453c2096196659c5d16bc136ed5df03bf768b`

AWS account: `654654474502` (control-plane release only)

AWS region: `us-east-1`

## Hosted diagnostic

- Deployed PR #556 at `a63453c2096196659c5d16bc136ed5df03bf768b`; protected
  plan `46046155250` and saved-plan apply `46047021652` succeeded.
- Migration verification passed; all six control-plane Lambdas are Active and
  Successful and match the exact release ZIP SHA-256. API health returned HTTP
  200 and authenticated CLI `/api/v1/me` confirmed workspace-admin access.
- Review-only revision `4907f919-ab29-4039-9e94-9fca1fd0b7f2` has the same
  content digest as the prior synthetic revision and `decision=null`.
- Plan-only run `96533832-bea0-47f5-89db-b006d9a3b8ed` failed before CodeBuild
  with safe issue `incompatible_health_target`; no artifact or Terraform plan
  exists. Raw proposal, plan, state, or credential values were not retrieved.

## Resources created

No customer workload AWS resources were created or changed. The hosted control
plane was changed only through its reviewed exact saved-plan release. No
customer review decision, workload apply, or destroy occurred.

## Commands executed

- Authenticated read-only status of run `96533832-bea0-47f5-89db-b006d9a3b8ed`;
  output was filtered to the safe `incompatible_health_target` issue.
- `pytest -q tests/test_generated_deployment_contract.py tests/test_terraform_generation.py`
  — 114 passed.
- Final `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`
  passed 2,084 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose
  checks. One existing Starlette deprecation warning. Documentation conventions
  and `git diff --check` passed. An earlier run found two stale v18 expectations;
  both now expect v19. Clean-room and PR CI remain pending.

## Observed result

The contract rejects `database_roundtrip` targeting `aws_rds_cluster` even
though it supports RDS-managed secret references and the first hosted scenario
requires relational data. The fix makes the supported target map explicit and
shared by the typed validator, prompt, and repair feedback.

## Teardown

No customer workload resources were created, so no teardown was needed.

## Local validation

- `pytest -q tests/test_generated_deployment_contract.py tests/test_terraform_generation.py` — 114 passed.
- `make verify` passed 2,084 tests, Ruff, Actions configuration, OpenAPI
  snapshot, and Compose checks. One existing Starlette deprecation warning.
- Documentation conventions and `git diff --check` passed. Clean-room cycle
  and PR CI remain pending.
- No AWS workload or generated Terraform plan was created by these local tests.

## Final boundary

This evidence identifies a contract mismatch only. It does not prove SQL
connectivity or read/write behavior, a saved plan, pricing, policy acceptance,
or any hosted customer lifecycle.
