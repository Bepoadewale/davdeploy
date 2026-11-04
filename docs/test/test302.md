# test302 — Typed DynamoDB-to-Lambda renderer binding

Date: 2026-11-04
Execution type: Local unit/contract tests, Terraform validation and fixture-backed clean-room cycle; no AWS workload.
Customer repository: `Bepoadewale/davdeploy`
Commit: `18d33e9` (`feat: bind DynamoDB output into Lambda renderer`)
AWS account: Not applicable; this PR creates no AWS resources.
AWS region: Not applicable.

## Resources created

- Detached clean-room worktree at `/tmp/davdeploy-cleanroom-pr302-20261104`.
- Dedicated virtual environment at `/tmp/davdeploy-pr302-venv`.
- Project-scoped Docker containers and network named `davdeploy-pr302-cleanroom`; PostgreSQL used `tmpfs`, no named volume.
- Temporary Compose file `/tmp/davdeploy-cleanroom-pr302-20261104/docker-compose.cleanroom.yml` with PostgreSQL data mounted to `tmpfs`.

## Commands executed

- `bash -n scripts/customer-workload-serverless-api.sh` — passed.
- `.venv/bin/ruff check apps/api/src/davdeploy/cloud_execution.py tests/test_cloud_execution.py tests/test_serverless_renderer_contract.py` — passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-serverless-api fmt -check` — passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-serverless-api validate` — passed.
- `scripts/terraform-validate.sh` — all configured roots passed.
- `make verify` — 506 passed, with the warning noted above.
- Clean-room commands, run with `COMPOSE_FILE=/tmp/davdeploy-cleanroom-pr302-20261104/docker-compose.cleanroom.yml` and `COMPOSE_PROJECT_NAME=davdeploy-pr302-cleanroom`:

  ```text
  make VENV=/tmp/davdeploy-pr302-venv bootstrap-local
  make VENV=/tmp/davdeploy-pr302-venv smoke api-contract customer-plan-e2e seed-demo-data demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check verify
  docker compose down --remove-orphans
  ```

  Bootstrap and each target passed. The full suite passed 506 tests; OpenAPI and Compose configuration checks passed. An initial disposable Compose override was rejected during config validation before creating resources; the corrected worktree-local Compose file used PostgreSQL `tmpfs` and passed.
- `GITHUB_PR_NUMBER=302 .venv/bin/python scripts/check_doc_conventions.py` — passed.
- Pull-request CI run [41779922484](https://github.com/Bepoadewale/davdeploy/actions/runs/41779922484) — all seven required checks passed on the preceding committed revision; this evidence update triggers another run.

## Observed result

The Lambda/API runner accepts only the declared S3 bucket and DynamoDB table input references, and validates each against the deterministic account/project/region naming contract before making AWS calls. The Terraform configuration passes the table name to the Lambda environment and grants only item-level/query actions on the exact table ARN. The DynamoDB renderer and API renderer remain disabled for ordinary hosted customer execution.

## Teardown

No AWS workload was deployed. `docker compose down --remove-orphans` removed only the named project containers and network. A follow-up query confirmed no `davdeploy-pr302-cleanroom` containers remain. PostgreSQL used `tmpfs`; no named Docker volume was created. The detached worktree, virtual environment, and Compose file are retained.

## Final boundary

This PR adds typed composition wiring and scoped IAM configuration. It does not prove that an application artifact uses DynamoDB successfully, does not certify the hosted CodeBuild runner, and does not enable customer deployment. A real composed AWS test remains required.
