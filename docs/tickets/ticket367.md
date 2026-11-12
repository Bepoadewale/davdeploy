# ticket367

PR: #367
Branch: security/nova-secret-output-path-367

## Problem / goal

Make Nova's typed `secret_reference` meaningful and provider-validated. Today the proposal can declare any computed string output as a secret reference, and the contract only supports a flat output name. Support a bounded RDS-managed Secrets Manager ARN output path without exposing secret values.

## Current repo state

- PR #365 rejects common literal credential and secret values in generated arguments unless represented as a typed `resource_reference` with `value_type=secret_reference`.
- `GeneratedOutput` and `ResourceReference` only accept flat attribute names; provider validation resolves only direct computed attributes.
- Nova's contract currently accepts a secret reference from any model-declared computed output; the plan policy/plan access profile remains separately gated.
- AWS provider lockfile pins `hashicorp/aws` 5.100.0.

## Research / references used

- `docs/tickets/ticket365.md` and `docs/test/test365.md`
- `apps/api/src/davdeploy/generated_deployment_contract.py`
- `apps/api/src/davdeploy/generated_provider_validation.py`
- `apps/api/src/davdeploy/terraform-provider.lock.hcl`
- AWS RDS-managed master password documentation: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html
- AWS `MasterUserSecret` API: https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_MasterUserSecret.html
- AWS provider 5.100 `aws_db_instance` schema documentation: https://registry.terraform.io/providers/hashicorp/aws/5.100.0/docs/resources/db_instance

## Work planned for the PR

- Add a strict, bounded grammar for provider output paths with literal zero index support for single-item nested output blocks.
- Resolve output paths through the pinned provider schema and require the leaf to be a computed output.
- Permit `secret_reference` declarations only for RDS-managed master-user secret ARN paths on RDS instance/cluster resources with `manage_master_user_password=true`.
- Permit secret ARNs only as values of Lambda environment variables whose names end in `_SECRET_ARN`.
- Reject secret-reference type forgery from unrelated computed fields and reject unsupported path syntax.
- Keep secret values out of proposals and Terraform configuration; generated references compile only to Terraform resource-output expressions.

## Acceptance criteria

- [x] Direct output references continue to validate and compile unchanged.
- [x] Only `aws_db_instance` and `aws_rds_cluster` RDS-managed `master_user_secret[0].secret_arn` paths can be declared as `secret_reference` outputs, and only when `manage_master_user_password=true`.
- [x] Secret ARNs can only be consumed by Lambda environment variables named with the `_SECRET_ARN` suffix.
- [x] Provider schema validation proves the nested path exists, is computed, and ends at a string attribute.
- [x] Unrelated computed outputs, unmanaged RDS passwords, and nonzero/unsupported indices fail closed.
- [x] Focused tests (50), Ruff, and `make verify` pass after the final consumer restriction.
- [x] Full local clean-room cycle passes.
- [x] Final-head required CI run `43136191166` passed all seven jobs.
- [x] Docs explain that plan-role support, runtime `GetSecretValue` authorization, external customer secret registration, and hosted execution remain follow-up work.

## Acceptance status

- [x] Implementation complete; focused tests (50), `make verify` (1,019 tests), Ruff, and pinned AWS provider 5.100.0 schema check pass.
- [x] Full clean-room cycle passed at code commit `ab90d6c66393d521560f00221857b8dfe619b710`.
- [x] Final-head required CI run `43136191166` passed all seven jobs for head `99215713dff1d859e3d235adeddf4456c05cc028`.

## Tests / validation performed

- `PYTHONPATH=apps/api/src .venv/bin/python -m pytest -q tests/test_nova_plan_access.py tests/test_generated_deployment_contract.py tests/test_generated_provider_validation.py` — 50 passed.
- `make lint` — passed.
- `make verify` — 1,019 tests passed; Actions configuration, Ruff, OpenAPI snapshot, and `docker compose config --quiet` passed. One existing Starlette/httpx deprecation warning remains.
- Final-head GitHub CI run [43136191166](https://github.com/Bepoadewale/davdeploy/actions/runs/43136191166) passed all seven required jobs for head `99215713dff1d859e3d235adeddf4456c05cc028`.
- Pinned schema check: initialized Terraform provider `hashicorp/aws` 5.100.0 from the repository lockfile and validated an RDS-managed secret ARN flowing into a Lambda `_SECRET_ARN` environment variable. Compiled value is only a Terraform reference expression.
- Full clean-room cycle passed in detached worktree `/private/tmp/davdeploy-pr367-cleanroom-20261112` at code commit `ab90d6c66393d521560f00221857b8dfe619b710`, with isolated Compose project `davdeploy-pr367-cleanroom-20261112` and a tmpfs Postgres override.
- Clean-room sequence: `clean-local`, `bootstrap-local`, `smoke`, `api-contract`, `customer-plan-e2e`, `seed-demo-data`, simple/complex/degraded/Day-2/policy-failure/readiness-failure demos, `trace-check`, `verify`, and final `clean-local`.
- Final absence checks confirmed no project containers, network, named volume, `.venv`, or `.local` remained. The worktree, override, and images remain retained.
- No AWS, Bedrock, customer plan/apply, or infrastructure changes occurred.

## Evidence files produced

- `docs/tickets/ticket367.md`
- `docs/test/test367.md`

## Boundaries

This PR must not enable Nova planning/apply, grant customer secret-read permissions, expose secret values, change the customer plan role, or claim end-to-end secret-backed workload support.

## Follow-up work

Implement exact-ARN scoped runtime access for an approved execution identity, tenant-scoped secret registration/reference binding, plan-role resource support where needed, and hosted customer evidence before enabling secret-backed deployments.
