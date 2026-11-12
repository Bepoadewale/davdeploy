# test367 — Nova typed secret-output validation

Date: 2026-11-12
Execution type: Static contract tests, pinned provider-schema validation, and isolated local clean-room proof
Customer repository: `Bepoadewale/davdeploy`
Commit: `ab90d6c66393d521560f00221857b8dfe619b710` (implementation)
AWS account: Not accessed
AWS region: Not accessed

## Change

Nova's generated proposal may declare `secret_reference` only for the nested RDS-managed master-password ARN on `aws_db_instance` or `aws_rds_cluster`, with `manage_master_user_password=true`. References can use a restricted nested output path containing only literal index zero. The path is resolved against the pinned AWS provider schema and must end in a computed string attribute. A reference can only populate a Lambda environment variable whose name ends in `_SECRET_ARN`. Terraform compilation emits only the trusted resource expression. Secret contents never appear in the proposal or generated configuration.

This does not add RDS to the Nova plan-access allowlist, retrieve a secret, grant `secretsmanager:GetSecretValue`, register customer-owned secrets, enable hosted planning/apply, or provide runtime integration. Those gates remain closed.

## Verification

- Focused suites: 50 passed across generated deployment contract, provider validation, and Nova plan access.
- `make lint`: passed.
- `make verify`: 1,019 tests passed; Actions configuration, Ruff, OpenAPI snapshot, and Compose config passed. One existing Starlette/httpx deprecation warning remains.
- Actual pinned provider schema check: Terraform initialized `hashicorp/aws` 5.100.0 from `apps/api/src/davdeploy/terraform-provider.lock.hcl`; an RDS-managed secret ARN flowing into a Lambda `_SECRET_ARN` environment variable passed schema validation. The compiled value was only the Terraform expression.
- Full clean-room cycle: passed in detached worktree `/private/tmp/davdeploy-pr367-cleanroom-20261112` at implementation commit `ab90d6c66393d521560f00221857b8dfe619b710`. Sequence covered clean, bootstrap, smoke, API contract, customer-plan E2E, seed data, simple/complex/degraded/Day-2/policy/readiness-failure demos, trace check, verify, and final clean.
- Required GitHub CI: pending.

## Observed result

The pinned schema accepted the RDS-managed ARN reference and rejected invalid output sources, unmanaged credentials, unsupported indices, and uses outside a Lambda `_SECRET_ARN` environment variable. Direct computed-output references still compile as before.

## Boundary

No AWS, Bedrock, customer plan/apply, or infrastructure mutation was performed. The provider schema download was a local CLI operation; it did not contact a customer account.

## Resources created

- No AWS resources or customer workload resources were created or changed.
- Terraform downloaded the locked AWS provider 5.100.0 and wrote its schema JSON under a PR-specific `/private/tmp/davdeploy-rds-schema367.*` directory. The directory is retained for reproducibility.
- The clean-room cycle used a separate, fresh Git worktree and a Compose override that mounted PostgreSQL data as tmpfs; no named volume was created.

## Commands executed

- `PYTHONPATH=apps/api/src .venv/bin/python -m pytest -q tests/test_nova_plan_access.py tests/test_generated_deployment_contract.py tests/test_generated_provider_validation.py`
- `make lint`
- `make verify`
- `terraform init -backend=false -input=false -lockfile=readonly -no-color` in a temporary schema workspace using `apps/api/src/davdeploy/terraform-provider.lock.hcl`
- `terraform providers schema -json` and a local validation of RDS managed secret ARN output flowing into a Lambda `_SECRET_ARN` environment variable
- Full clean-room cycle ran `clean-local`, `bootstrap-local`, `smoke`, `api-contract`, `customer-plan-e2e`, `seed-demo-data`, `demo-simple`, `demo-complex`, `demo-degraded`, `demo-day2`, `demo-failure`, `demo-readiness-failure`, `trace-check`, `verify`, and final `clean-local`.
- `python scripts/check_doc_conventions.py`
- `git diff --check`

## Teardown

- No cloud resources were created, so no cloud teardown was needed.
- The temporary provider schema directory and provider cache remain retained. Only the exact clean-room project's containers and network were removed; no other project data was deleted.
- The clean-room project's containers and network were stopped and removed by its final scoped `clean-local`; its tmpfs database left no volume. Absence checks found no project containers/network/volume, worktree `.venv`, or `.local`.

## Limitations

This is contract and provider-schema evidence only. It does not enable RDS in the Nova plan-access profile, grant runtime `secretsmanager:GetSecretValue`, register existing customer secrets, or prove a hosted secret-backed workload.

## Final boundary

The overall Nova customer workflow remains disabled and unproven. This change does not authorize any customer plan, apply, health check, recovery, or teardown.
