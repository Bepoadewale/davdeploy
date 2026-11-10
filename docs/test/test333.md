# test333 — tenant-scoped Nova plan history

Date: 2026-11-10
Execution type: Local API/service tests and static contract verification; no customer workload
Customer repository: N/A; no customer repository or workload was used
Commit: `43ba947`
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Resources created

No AWS or customer resources were created. Tests use local SQLite databases and
temporary directories. The isolated clean-room run used the PR-specific Compose
project `davdeploy-pr333-cleanroom-20261110`.

## Commands executed

```text
uv run pytest tests/test_nova_plan_runs.py -q
uv run ruff check apps/api/src/davdeploy/main.py apps/api/src/davdeploy/service.py tests/test_nova_plan_runs.py
make openapi-update
make openapi-check
python scripts/check_doc_conventions.py
git diff --check
make verify
COMPOSE_PROJECT_NAME=davdeploy-pr333-cleanroom-20261110 make local-proof  # e046917 and final source 43ba947
COMPOSE_PROJECT_NAME=davdeploy-pr333-cleanroom-20261110 make clean-local
```

## Observed result

- Focused plan-run suite: 40 passed.
- Ruff passed for the touched runtime and test files.
- OpenAPI snapshot was updated for the new read-only project history route and
  `make openapi-check` passed.
- Full `make verify` passed: 865 tests; Ruff, Actions configuration, OpenAPI,
  and Docker Compose configuration passed.
- Documentation convention validation and `git diff --check` passed.
- Fresh isolated `make local-proof` passed on commit `e046917`: bootstrap,
  smoke, API contract, customer-plan E2E, demo data seed, trace check, and all
  865 tests. The customer-plan E2E used local fixtures; no AWS infrastructure
  was deployed.
- After adding plan title and revision number to each history entry, the full
  clean-room cycle was repeated on final runtime commit `43ba947`; bootstrap,
  smoke, API contract, customer-plan E2E, seed, trace check, and all 865 tests
  passed again.
- `make clean-local` removed the exact PR #333 Compose containers, network,
  PostgreSQL volume, `.venv`, and `.local`. Docker inspection and filesystem
  checks confirmed these targets were absent afterward. The unrelated existing
  `davdeploy-nova-cleanroom-20261105a` container was left untouched.
- GitHub Actions run `42890326037` passed all seven required checks for final
  PR head `4244757`, including the fresh-runner `local-e2e` and `cloud-contracts`
  jobs.
- No AWS, Bedrock, CodeBuild, state API, or customer workload calls occurred.

## Teardown

No cloud resources were created. Local temporary test data is managed by the
test framework. The PR-specific clean-room stack was cleaned with
`make clean-local`, and its cleanup was verified.

## Final boundary

This proves local read-only plan-history API behavior, authorization filters,
stable pagination, safe response fields, and stale preparation status
reconciliation. It does not prove hosted deployment, remote state, pricing,
approval, apply, health, recovery, or teardown.
