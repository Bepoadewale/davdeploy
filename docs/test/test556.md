# test556 — strict managed database secret reference repair

Date: 2026-11-27
Execution type: Authenticated hosted status read, local tests, and isolated clean-room validation; no customer AWS workload
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance case)
Commit: `0078bc90d41d2c9a20242e88a2d7d2f6f430f8b4` (PR #556)
AWS account: `654654474502` (control-plane release only)
AWS region: `us-east-1`

## Resources created

No customer workload AWS resources were created. The v18 run failed before CodeBuild and produced no artifact.

## Commands executed

- Authenticated read-only `GET /api/v1/generated-plan-runs/3b5b2a3e-96f8-4167-9af9-ea1c5ccdebb6`: `FAILED`, no artifact, prompt v18, two attempts/one repair, safe `credential_value` at `resources[*]`.
- No raw proposal, credential value, plan/state bytes, or customer workload was retrieved or created.
- Final-head focused tests passed (62), including malformed non-string resource-type bounded-repair regression.
- Final-head `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python` passed 2,081 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose checks. One existing Starlette deprecation warning.
- Full clean-room cycle passed in `/private/tmp/davdeploy-nova-556-cleanroom` at this commit with a dedicated Compose project and tmpfs PostgreSQL. Bootstrap, smoke, API contract, customer-plan E2E, seed, all required demo variants, trace check, and full verify passed. Final clean removed only the run's scoped containers/network, `.local`, and external venv; absence checks passed. Worktree and compose override are retained.
- PR CI run `46043864593`: all seven required checks passed. Documentation conventions and diff checks passed.

## Observed result

ID validation passed after deterministic normalization. Generation then failed on a secret-like resource argument. PR #556 converts only a uniquely identifiable Lambda secret ARN variable to a typed reference to the single RDS-managed master-secret output. Other shapes remain invalid. A malformed non-string resource type now reaches strict validation and bounded Nova repair instead of raising during normalization.

## Teardown

No workload resources were created, so no teardown was needed. The terminal run remains as evidence.

## Final boundary

This is diagnostic evidence only; there is no plan artifact or customer workload. No review approval, apply, or destroy occurred.
