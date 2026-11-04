# test303 — Executor dispatcher DynamoDB input

Date: 2026-11-04
Execution type: Local dispatcher unit tests, full suite and fixture-backed clean-room cycle; no AWS workload.
Customer repository: `Bepoadewale/davdeploy`
Commit: `62a027b` (`fix: dispatch typed DynamoDB API input`)
AWS account: Not applicable; this PR creates no AWS resources.
AWS region: Not applicable.

## Resources created

- No AWS resources.
- Detached clean-room worktree at `/tmp/davdeploy-cleanroom-pr303-20261104`.
- Dedicated virtual environment at `/tmp/davdeploy-pr303-venv`.
- Project-scoped containers and network named `davdeploy-pr303-cleanroom`; PostgreSQL used `tmpfs`, with no named volume.
- Temporary Compose file `/tmp/davdeploy-cleanroom-pr303-20261104/docker-compose.cleanroom.yml` with PostgreSQL data mounted to `tmpfs`.

## Commands executed

- `.venv/bin/pytest tests/test_renderer_dispatcher.py -q` — 11 passed.
- `.venv/bin/ruff check tests/test_renderer_dispatcher.py` — passed.
- `bash -n scripts/customer-workload-dispatcher.sh` — passed.
- `make verify` — 507 passed; OpenAPI and Compose configuration passed; one existing Starlette/httpx deprecation warning.
- `GITHUB_PR_NUMBER=303 .venv/bin/python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Clean-room commands, run with `COMPOSE_FILE=/tmp/davdeploy-cleanroom-pr303-20261104/docker-compose.cleanroom.yml` and `COMPOSE_PROJECT_NAME=davdeploy-pr303-cleanroom`:

  ```text
  make VENV=/tmp/davdeploy-pr303-venv bootstrap-local
  make VENV=/tmp/davdeploy-pr303-venv smoke api-contract customer-plan-e2e seed-demo-data demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check verify
  docker compose down --remove-orphans
  ```

  Bootstrap and each target passed; the complete suite passed 507 tests. OpenAPI and Compose configuration checks passed.
- Pull-request CI: pending.

## Observed result

The dispatcher accepts the declared S3 bucket and DynamoDB table input/output port pairs for the Lambda/API renderer. Missing inputs, extra keys and incorrect source output names fail before the runner is invoked. Existing gates remain explicit; no customer execution route is enabled by this change.

## Teardown

No AWS workload was deployed. `docker compose down --remove-orphans` removed only the named project containers and network. A follow-up query confirmed no `davdeploy-pr303-cleanroom` containers remain. PostgreSQL used `tmpfs`, and no named Docker volume was created. The detached worktree, virtual environment, and Compose file are retained.

## Final boundary

This proves local dispatcher contracts only. It does not certify Lambda data access, hosted worker recovery, or any customer deployment. Real composed AWS evidence remains required.
