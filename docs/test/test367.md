# test367 — Nova typed secret-output validation

Date: 2026-11-12
Execution type: Static contract tests, pinned provider-schema validation, and isolated local clean-room proof
Customer repository: `Bepoadewale/davdeploy`
Commit: Pending implementation commit
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
- Full clean-room cycle: pending.
- Required GitHub CI: pending.

## Observed result

The pinned schema accepted the RDS-managed ARN reference and rejected invalid output sources, unmanaged credentials, unsupported indices, and uses outside a Lambda `_SECRET_ARN` environment variable. Direct computed-output references still compile as before.

## Boundary

No AWS, Bedrock, customer plan/apply, or infrastructure mutation was performed. The provider schema download was a local CLI operation; it did not contact a customer account.

## Resources created

- No AWS resources or customer workload resources were created or changed.
- Terraform downloaded the locked AWS provider 5.100.0 and wrote its schema JSON under a PR-specific `/private/tmp/davdeploy-rds-schema367.*` directory. The directory is retained for reproducibility.

## Commands executed

- `PYTHONPATH=apps/api/src .venv/bin/python -m pytest -q tests/test_nova_plan_access.py tests/test_generated_deployment_contract.py tests/test_generated_provider_validation.py`
- `make lint`
- `make verify`
- `terraform init -backend=false -input=false -lockfile=readonly -no-color` in a temporary schema workspace using `apps/api/src/davdeploy/terraform-provider.lock.hcl`
- `terraform providers schema -json` and a local validation of RDS managed secret ARN output flowing into a Lambda `_SECRET_ARN` environment variable
- Full clean-room cycle: pending
- `python scripts/check_doc_conventions.py`
- `git diff --check`

## Teardown

- No cloud resources were created, so no cloud teardown was needed.
- The temporary provider schema directory and provider cache remain retained; no local files or Docker resources were deleted.

## Limitations

This is contract and provider-schema evidence only. It does not enable RDS in the Nova plan-access profile, grant runtime `secretsmanager:GetSecretValue`, register existing customer secrets, or prove a hosted secret-backed workload.

## Final boundary

The overall Nova customer workflow remains disabled and unproven. This change does not authorize any customer plan, apply, health check, recovery, or teardown.
