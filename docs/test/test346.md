# test346 — paginated customer plan revision history

PR: [#346](https://github.com/Bepoadewale/davdeploy/pull/346)

Date: 2026-11-11
Execution type: Local automated tests only; no customer workload run
Customer repository: `Bepoadewale/davdeploy` (repository implementation tests)
Commit: `0d2ce0b61faf20cef94382a6b1b71d50df57205a` (implementation)
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Scope

Local automated validation of the project-scoped, read-only customer plan
revision history API. The tests cover deterministic cursor pagination,
creator/admin visibility, cross-project and cross-tenant denial, malformed
cursors, page bounds, and response fields that exclude plan content and
internal subject IDs.

## Results

- `uv run pytest tests/test_workspace_dashboards.py -q`: 9 passed.
- `uv run ruff check apps/api/src/davdeploy/main.py apps/api/src/davdeploy/service.py tests/test_workspace_dashboards.py`: passed.
- `make verify`: 880 passed; Ruff, Actions configuration, OpenAPI snapshot, and Docker Compose checks passed.
- `make openapi-check`: passed.
- GitHub required checks and review: pending for the current PR head.

## Resources created

No AWS or customer resources were created. Local unit tests use their normal
temporary in-memory database fixtures.

## Commands executed

- `uv run pytest tests/test_workspace_dashboards.py -q`
- `uv run ruff check apps/api/src/davdeploy/main.py apps/api/src/davdeploy/service.py tests/test_workspace_dashboards.py`
- `make verify`
- `make openapi-check`

## Observed result

Revision pagination, visibility, cursor denial, bounds, safe fields, Ruff,
OpenAPI, and all 880 backend tests passed locally. Hosted GitHub checks remain
pending.

## Teardown

No cloud resources were created; no teardown was needed. Test database fixtures
are in memory and end with the test process.

## Final boundary

This is local test evidence only. No AWS, Bedrock, CodeBuild, customer role,
saved-plan, customer infrastructure, apply, health, or teardown operation was
performed. The endpoint reports plan revision summaries only; it does not
claim that Terraform planning or deployment has occurred.
