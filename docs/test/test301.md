# test301 — Gated DynamoDB table renderer

Date: 2026-11-04
Execution type: Local tests, Terraform validation and fixture-backed clean-room cycle; no AWS workload.
Customer repository: `Bepoadewale/davdeploy`
Commit: `64ca498` (`feat: add gated DynamoDB workload renderer`)
AWS account: Not applicable; no AWS credentials or resources used.
AWS region: Not applicable.

## Resources created

- Detached clean-room worktree at `/tmp/davdeploy-cleanroom-pr301-20261104`.
- Dedicated virtual environment at `/tmp/davdeploy-pr301-venv`.
- Project-scoped Docker containers and network using `davdeploy-pr301-cleanroom`; PostgreSQL data used `tmpfs`, with no named volume.
- Terraform provider cache under the ignored DynamoDB root.
- Executor package artifacts at `/tmp/davdeploy-pr301-executor.zip`, `/tmp/davdeploy-pr301-executor-v2.zip` and `/tmp/davdeploy-pr301-executor-final.zip`.
- No AWS resources.

## Commands executed

- `bash -n scripts/customer-workload-dynamodb.sh scripts/customer-workload-dispatcher.sh scripts/build_customer_executor_package.sh scripts/terraform-validate.sh` — passed.
- Ruff on changed Python/test files — passed.
- Focused tests — 100 passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-dynamodb init -backend=false -input=false` and `validate` — passed with AWS provider 5.100.0, pinned in `.terraform.lock.hcl`.
- `scripts/terraform-validate.sh` — all configured roots initialized and validated, including the private S3 and DynamoDB renderer roots.
- `make verify` — 505 passed; OpenAPI snapshot and Compose configuration passed. One existing Starlette/httpx deprecation warning was reported.
- `scripts/build_customer_executor_package.sh /tmp/davdeploy-pr301-executor-final.zip` and inspection with `unzip -l` — passed; archive contains the final DynamoDB runner, Terraform root, dispatcher and provider lock file.
- `GITHUB_PR_NUMBER=301 python3.12 scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Clean-room cycle at `22d0dfa`:

  ```text
  git worktree add --detach /tmp/davdeploy-cleanroom-pr301-20261104 64ca498
  COMPOSE_FILE='/tmp/davdeploy-cleanroom-pr301-20261104/docker-compose.yml:/tmp/davdeploy-pr301-compose-overlay.yml' COMPOSE_PROJECT_NAME=davdeploy-pr301-cleanroom make -C /tmp/davdeploy-cleanroom-pr301-20261104 VENV=/tmp/davdeploy-pr301-venv bootstrap-local
  COMPOSE_FILE='/tmp/davdeploy-cleanroom-pr301-20261104/docker-compose.yml:/tmp/davdeploy-pr301-compose-overlay.yml' COMPOSE_PROJECT_NAME=davdeploy-pr301-cleanroom make -C /tmp/davdeploy-cleanroom-pr301-20261104 VENV=/tmp/davdeploy-pr301-venv smoke api-contract customer-plan-e2e seed-demo-data demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check verify
  COMPOSE_FILE='/tmp/davdeploy-cleanroom-pr301-20261104/docker-compose.yml:/tmp/davdeploy-pr301-compose-overlay.yml' COMPOSE_PROJECT_NAME=davdeploy-pr301-cleanroom docker compose down --remove-orphans
  ```

  Bootstrap and every listed target passed, including 505 tests. The overlay made PostgreSQL storage ephemeral `tmpfs`; teardown removed only this named Compose project's containers and network.
- Pull-request CI run [41777364015](https://github.com/Bepoadewale/davdeploy/actions/runs/41777364015) — all seven required checks passed on the preceding committed revision. This evidence-file update is being revalidated by the current PR checks.

## Observed result

- The fixed `aws-nosql-data` renderer creates one deterministic, project-scoped DynamoDB table with pay-per-request billing, encryption at rest, point-in-time recovery and a string partition key.
- The Terraform account guard compares the active identity with the approved account. Table tags bind it to DavDeploy, connection, project and plan; the Terraform state key also includes region.
- The runner accepts only its fixed lifecycle operations, uses a project/plan-scoped saved plan with a SHA-256 check, and reports only the declared non-sensitive table name and ARN.
- The destroy preflight sends one non-paginated scan request for at most one item and refuses destruction if it finds data or cannot prove the scan is complete. The same preflight runs immediately before the saved destroy plan is applied. Cleanup verification checks that the table is absent and Terraform state is empty.
- Observe confirms active state, on-demand billing, encryption, point-in-time recovery and project/plan tags. It allows up to ten minutes for new-table point-in-time recovery to become enabled.
- The renderer is not enabled for ordinary customer execution. Its dispatcher route requires the explicit DynamoDB hosted-certification environment flag; the backend permits it only in the persisted certification mode.
- The renderer currently has no live regional price lookup. Customer-facing estimates must include on-demand requests, data storage and PITR backup size; AWS bills PITR based on table size ([DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/)). This remains a pre-customer follow-up.

## Teardown

- No AWS resources existed to tear down.
- `docker compose down --remove-orphans` removed only the `davdeploy-pr301-cleanroom` containers and network. A follow-up container query found no containers with that project prefix.
- No named Docker volume was created or deleted. The worktree, virtual environment, provider cache, package archives and Docker images are retained.

## Final boundary

This proves code contracts, Terraform configuration validity, executor packaging and local fixture behavior. It does not certify a live DynamoDB table lifecycle, a real data-plane request, hosted CodeBuild execution, or customer deployment. The renderer remains gated until an isolated real AWS test records table readiness, request behavior, destroy and independent absence verification.
