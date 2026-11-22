# test445 — SQS retry, DLQ, and Lambda consumer plan policy

- Date: 2026-11-22
- Execution type: Local generated-plan policy regression and Terraform module validation
- Repository: `Bepoadewale/davdeploy`
- Customer repository: N/A; synthetic plan fixtures only
- Commit: local PR #445 working tree based on `7f9148a12cb5ec91ed7c5e19c49a1ce8c7980c98` (PR #444)
- Pull request: [#445](https://github.com/Bepoadewale/davdeploy/pull/445)
- AWS account: Not used
- AWS region: Not used

## Resources created

None. No AWS API, Terraform plan, apply, destroy, Terraform state, hosted
control-plane runtime, customer credential, or Nova execution gate was used or
changed. The local Terraform module validation initialized the AWS provider
without a backend and ran `terraform validate` only.

## Commands executed

- `PYTHONPATH=apps/api/src .venv-pr399/bin/python -m pytest tests/test_generated_plan_policy.py tests/test_sqs_plan_pricing.py tests/test_generated_plan_pricing.py -q` — 396 passed.
- `.venv-pr399/bin/ruff check apps/api/src/davdeploy/domain.py apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py` — passed.
- `make openapi-check` — passed; the API snapshot matches.
- `terraform -chdir=infrastructure/terraform/module-validation/events validate` — passed.
- `terraform fmt -check infrastructure/terraform/modules/sqs-queue/main.tf` — passed.
- `git diff --check` — passed.
- `make api-contract` — could not complete because its local API request to `127.0.0.1:8080` had no server listening. The snapshot check passed; CI remains required for the full contract workflow.

## Observed result

The local policy fixtures verify bounded plan-known one-to-one source/DLQ
pairs, retry count, queue retention and visibility, Lambda timeout/batch-window
relationship, and exact inline consumer-role SQS permissions. Unsupported
managed-policy and module-output-only consumer bindings remain fail-closed.
These are source-level checks only and do not demonstrate SQS delivery,
idempotency, producer access, complete effective permissions, or AWS lifecycle.

PR #437's isolated same-account ECS Express lifecycle evidence remains accepted
for the general customer-side plan/apply/health/update/recovery/teardown gate.
It is separate from these SQS tests and does not establish Nova dispatch or
Nova-generated workload evidence.

## Teardown

None. No cloud resources were created.

## Final boundary

No deployment or customer workload is claimed. Hosted SQS lifecycle, Nova
dispatch/authorization/credential evidence, broader policy coverage, and
complete cost coverage remain open.
