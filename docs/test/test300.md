# test300 — Typed private-storage input to the serverless API renderer

Date: 2026-11-04
Execution type: Local tests, Terraform validation and clean-room fixture cycle; no AWS workload.
Customer repository: `Bepoadewale/davdeploy`
Commit: `c56f873` (`feat: resolve typed storage inputs for lambda renderer`)
AWS account: Not applicable; no AWS credentials or resources used.
AWS region: Not applicable.

## Resources created

- A dedicated Python virtual environment at `/tmp/davdeploy-pr300-venv`.
- A detached clean-room worktree at `/tmp/davdeploy-cleanroom-pr300-20261104`.
- Project-scoped Docker containers and network using `davdeploy-pr300-cleanroom`; PostgreSQL storage was `tmpfs`, with no named volume.
- Terraform's local provider cache under the ignored serverless API Terraform root.
- No AWS resources.

## Commands executed

- `uv run ruff check ...` on changed Python and test files — passed.
- `bash -n scripts/customer-workload-serverless-api.sh scripts/customer-workload-dispatcher.sh` — passed.
- Focused tests: `uv run pytest -q tests/test_module_ports.py tests/test_module_renderers.py tests/test_renderer_dispatcher.py tests/test_serverless_renderer_contract.py tests/test_cloud_execution.py` — 96 passed.
- `make verify` — 498 passed; OpenAPI snapshot matched and Compose configuration passed. One existing Starlette/httpx deprecation warning was reported.
- `terraform fmt -check infrastructure/terraform/customer-workload-serverless-api` — passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-serverless-api validate` — passed.
- `GITHUB_PR_NUMBER=300 python3.12 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Clean-room cycle at `c56f873`:

  ```text
  git worktree add --detach /tmp/davdeploy-cleanroom-pr300-20261104 c56f873
  COMPOSE_FILE='/tmp/davdeploy-cleanroom-pr300-20261104/docker-compose.yml:/tmp/davdeploy-pr300-compose-overlay.yml' COMPOSE_PROJECT_NAME=davdeploy-pr300-cleanroom make -C /tmp/davdeploy-cleanroom-pr300-20261104 VENV=/tmp/davdeploy-pr300-venv bootstrap-local
  COMPOSE_FILE='/tmp/davdeploy-cleanroom-pr300-20261104/docker-compose.yml:/tmp/davdeploy-pr300-compose-overlay.yml' COMPOSE_PROJECT_NAME=davdeploy-pr300-cleanroom make -C /tmp/davdeploy-cleanroom-pr300-20261104 VENV=/tmp/davdeploy-pr300-venv smoke api-contract customer-plan-e2e seed-demo-data demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check verify
  COMPOSE_FILE='/tmp/davdeploy-cleanroom-pr300-20261104/docker-compose.yml:/tmp/davdeploy-pr300-compose-overlay.yml' COMPOSE_PROJECT_NAME=davdeploy-pr300-cleanroom docker compose down --remove-orphans
  ```

  All targets passed, including 498 tests. The PostgreSQL overlay used `tmpfs`; cleanup removed only containers and network for the named project. No named volume was created or deleted.
- Pull-request CI run [41773250123](https://github.com/Bepoadewale/davdeploy/actions/runs/41773250123) — all seven checks passed for the implementation, ticket and evidence file.

## Observed result

- The durable worker resolves a module's declared input references only from successful dependency outputs and validates them against the consumer module's declared input ports.
- The fixed CodeBuild adapter sends the validated input to the selected module only. Reserved input values supplied through the ordinary execution environment are discarded.
- The only permitted input binding in this version is `aws-file-storage.bucket_name` to `aws-serverless-api.uploads_bucket_name`. The dispatcher and API runner validate its type and exact project/account/region-derived bucket name.
- Lambda receives `UPLOADS_BUCKET_NAME` and an IAM policy scoped to that bucket and its objects. No user-controlled bucket value, command, or Terraform input is accepted.
- Resolved values are not included in user-facing failure details or audit events.
- Both renderers remain unavailable for ordinary customer execution. The explicit hosted-certification gate is still required.

## Teardown and retained items

- No AWS resources existed to tear down.
- `docker compose down --remove-orphans` removed the test project's containers and network; a follow-up `docker ps` query found no containers with the project prefix.
- No named Docker volume was used. The Python environment and clean-room worktree are retained for reproducibility; Docker images are retained.

## Final boundary

This evidence proves local code contracts, Terraform configuration validity and fixture-backed clean-room behavior. It does not certify a real composed S3-to-Lambda deployment, hosted CodeBuild execution, customer enablement, or rollback/absence behavior in AWS. Those remain prerequisites for enabling the renderers.
