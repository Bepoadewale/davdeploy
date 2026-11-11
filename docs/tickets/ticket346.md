# ticket346 — paginated customer plan revision history

PR: [#346](https://github.com/Bepoadewale/davdeploy/pull/346)
Branch: `feat/customer-plan-revision-history-346`
Base: `main`

## Problem / goal

Let an authorized project member retrieve all customer plan revisions through a bounded, tenant-scoped cursor API. The dashboard currently returns only its newest 20 revisions. This endpoint complements the existing paginated Nova run-status API; it does not add apply, approval, pricing, health, recovery, or teardown behavior.

## Current repo state

- `GET /api/v1/dashboard` limits plan revisions to 20.
- `GET /api/v1/projects/{project_id}/generated-plan-runs` pages Nova run status, but does not list revisions with no Nova run.
- Revision detail is available by exact ID and validates organization/project ownership.

## Research / references used

- `ProductService.workspace_dashboard()` and revision detail authorization in `service.py`.
- Existing cursor and visibility conventions in `generated_plan_run_history()`.
- Existing customer plan detail endpoint and dashboard projection.

## Work planned for the PR

- Add a read-only project-scoped plan-revision history endpoint with stable cursor pagination and a bounded page size.
- Preserve workspace-administrator and plan-creator visibility; authorize cursor anchors under the same project and visibility rules.
- Return only customer-safe plan summary fields and avoid exposing internal subjects or plan content.
- Add service/route tests and update OpenAPI plus PR evidence.

## Acceptance criteria

- [x] Authorized customers can page through all visible revisions in deterministic order.
- [x] Cross-tenant, cross-project, and invisible creator records/cursors are denied without disclosure.
- [x] Invalid cursors and page limits fail safely; response contains no private plan content.
- [x] Focused and full local verification pass; PR checks remain the merge gate.
- [x] No AWS calls or customer infrastructure mutations are made.

## Acceptance status

Implementation and local checks pass. The required GitHub checks and review are
still pending and remain the merge gate.

## Tests / validation performed

- `uv run pytest tests/test_workspace_dashboards.py -q`: 9 passed.
- `uv run ruff check apps/api/src/davdeploy/main.py apps/api/src/davdeploy/service.py tests/test_workspace_dashboards.py`: passed.
- `make verify`: 880 passed; Ruff, OpenAPI v1 snapshot, Actions configuration, and Docker Compose configuration passed. One existing Starlette/httpx deprecation warning remains.
- `make openapi-check`: passed.
- `git diff --check`: passed before final push.
- GitHub CI/review: pending for current PR head.
- No AWS, Bedrock, CodeBuild, customer role, or infrastructure calls were made.

## Evidence files produced

- [docs/test/test346.md](../test/test346.md)

## Boundaries

This improves history discoverability only. Nova saved-plan pricing/approval, hosted apply, health, recovery, and destroy remain separate unmet gates. Frontend integration may consume this endpoint in a later focused PR.

## Follow-up work

Consume the revision and Nova run history APIs in the customer history page after this backend contract is merged. Keep apply, health, recovery, and teardown labels tied to their future backend evidence.
