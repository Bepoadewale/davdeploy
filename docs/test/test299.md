# test299 — Private S3 renderer contract

Date: 2026-11-04
Execution type: Local tests and Terraform validation; no AWS workload.
Customer repository: `Bepoadewale/davdeploy`
Commit: `e42c4e2` (`feat: add gated private S3 workload renderer`)
AWS account: Not applicable; no AWS credentials or resources used.
AWS region: Not applicable.

## Resources created

- A Terraform provider cache under the new module root's ignored `.terraform/` directory.
- No AWS resources.

## Commands executed

- `terraform fmt infrastructure/terraform/customer-workload-private-s3` — passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-private-s3 init -backend=false -input=false` — passed; selected AWS provider `5.100.0`, recorded in `.terraform.lock.hcl`.
- `terraform -chdir=infrastructure/terraform/customer-workload-private-s3 validate` — passed.
- `bash -n scripts/customer-workload-private-s3.sh scripts/customer-workload-dispatcher.sh scripts/build_customer_executor_package.sh` — passed.
- `uv run ruff check ...` on changed Python and tests — passed.
- `uv run pytest -q tests/test_module_ports.py tests/test_module_renderers.py tests/test_private_s3_renderer_contract.py tests/test_renderer_dispatcher.py tests/test_planner_decisions.py` — 61 passed.
- `make verify` — 491 passed, one existing Starlette deprecation warning; OpenAPI snapshot and Compose config passed.
- `GITHUB_PR_NUMBER=299 python3.12 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Clean-room cycle at commit `e42c4e2` — bootstrap, service smoke, API contract, customer-plan E2E, seed data, simple/complex/Day-2/degraded/policy/readiness demos, trace check and full `make verify` all passed (491 tests; one existing warning).

Clean-room commands used a unique Compose project with a tmpfs override for
PostgreSQL; the `/tmp` virtual environment is intentionally retained:

```text
git worktree add --detach /tmp/davdeploy-cleanroom-pr299-20261104 e42c4e2
COMPOSE_FILE='/tmp/davdeploy-cleanroom-pr299-20261104/docker-compose.yml:/tmp/davdeploy-pr299-compose-overlay.yml' COMPOSE_PROJECT_NAME=davdeploy-pr299-cleanroom make -C /tmp/davdeploy-cleanroom-pr299-20261104 VENV=/tmp/davdeploy-pr299-venv bootstrap-local
COMPOSE_FILE='/tmp/davdeploy-cleanroom-pr299-20261104/docker-compose.yml:/tmp/davdeploy-pr299-compose-overlay.yml' COMPOSE_PROJECT_NAME=davdeploy-pr299-cleanroom make -C /tmp/davdeploy-cleanroom-pr299-20261104 VENV=/tmp/davdeploy-pr299-venv smoke api-contract customer-plan-e2e seed-demo-data demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check verify
COMPOSE_FILE='/tmp/davdeploy-cleanroom-pr299-20261104/docker-compose.yml:/tmp/davdeploy-pr299-compose-overlay.yml' COMPOSE_PROJECT_NAME=davdeploy-pr299-cleanroom docker compose down --remove-orphans
```

## Observed result

- Terraform formatting and validation passed. Focused tests passed (61 tests); full `make verify` passed (491 tests) with one existing Starlette deprecation warning.
- The Terraform configuration sets an account guard, project/connection/plan tags, S3 public access blocks, bucket-owner-enforced ownership, AES256 encryption, versioning and a policy denying insecure transport.
- `force_destroy = false`; the runner checks all current and previous object versions before planning or applying destroy, so a non-empty customer bucket is not automatically emptied.
- Terraform state, saved plans and result artifacts are constrained to connection/project and plan/run prefixes. Apply uses a saved plan and checks its SHA-256 digest.
- Output normalization accepts only declared, non-sensitive `bucket_name` and `bucket_arn` outputs.
- The renderer is disabled in the Python registry. The dispatcher has a separate off-by-default certification gate, which the production adapter does not set.

The clean-room Compose project used `tmpfs` for PostgreSQL storage; it created no named database volume. The isolated executor image builds completed successfully.

## Teardown

No AWS resources were created, so no AWS teardown was needed. The clean-room services used a unique Compose project and ephemeral PostgreSQL storage. Its project containers and network were stopped and removed with `docker compose down --remove-orphans`; no named volume was created or deleted. Docker images and the isolated `/tmp/davdeploy-pr299-venv` were retained. The validation worktree remains at `/tmp/davdeploy-cleanroom-pr299-20261104` for reproducibility. The Terraform provider cache remains ignored under the module root.

## Final boundary

No AWS resource was created, updated, observed, or destroyed. This evidence proves configuration and local contracts only. It does not certify a live bucket lifecycle, hosted worker dispatch, input binding, rollback, or composed customer deployment.
