# ticket334 — filter Nova plan history by exact revision

PR: [#334](https://github.com/Bepoadewale/davdeploy/pull/334)
Branch: `feat/generated-plan-history-revision-filter-334`
Base: `main`

## Problem / goal

Let the customer workflow request plan-run history for one exact approved
revision. A project can have many runs, so reading only the newest project
page can incorrectly make an older revision appear to have no run.

## Current repo state

- PR #333 added a tenant-scoped, paginated `GET
  /api/v1/projects/{project_id}/generated-plan-runs` route.
- The route returns safe plan status and customer-facing title/revision labels,
  but only filters by project. The frontend post-approval page needs exact
  revision filtering to report the correct Terraform plan state.
- The customer plan revision detail response also needs its project ID so the
  customer page can call the project history route without an extra dashboard
  lookup.
- Planning remains review-only; pricing, approval, apply, health, recovery,
  and teardown remain unavailable.

## Research / references used

- Existing plan history service and safe projection:
  `ProductService.generated_plan_run_history()`.
- Tenant-owned revision/project relationship:
  `InfrastructurePlanRevision` and `InfrastructurePlan` models.
- Backend route and query-parameter conventions in `apps/api/src/davdeploy/main.py`.

## Work planned for the PR

- Add an optional `revision_id` query parameter to the project history API.
- Include the owning project ID in customer revision detail.
- Verify that the exact revision belongs to the authenticated organization
  and requested project before querying runs.
- Bind both returned items and cursor anchors to the same revision filter.
- Test exact matches, invalid/foreign revision denial, and cursor isolation.
- Keep the endpoint read-only and preserve all execution gates.

## Acceptance criteria

- [x] An authorized customer can request history for one exact revision.
- [x] A revision from another project or tenant cannot be queried or used as
      a cursor scope.
- [x] Pagination remains deterministic and bound to the selected revision.
- [x] Existing project-wide history behavior remains unchanged when the
      filter is omitted.
- [x] No approval, apply, health, recovery, or teardown capability is added.

## Acceptance status

Implementation is complete. Focused and full local verification, OpenAPI
checks, and the isolated clean-room cycle passed. Current-head CI is pending;
no hosted state or workload execution is claimed.

## Tests / validation performed

- `uv run pytest tests/test_nova_plan_runs.py -q`: 41 passed.
- `uv run pytest tests/test_customer_plan_review.py -q`: 32 passed, including
  the project ID response field.
- `make verify`: 866 passed; Ruff, Actions configuration, OpenAPI, and Docker
  Compose configuration passed.
- `make openapi-check`, documentation conventions, and `git diff --check`
  passed.
- Clean-room `make local-proof` passed at `338a403`; current-head `make verify`
  passed with 866 tests. GitHub CI is pending.
- Runtime evidence: `docs/test/test334.md`.

## Evidence files produced

- `docs/test/test334.md` records the local-only implementation boundary.

## Boundaries

No AWS, Bedrock, CodeBuild, state API, or customer workload calls are needed.
This does not make plans approvable or enable deployment.

## Follow-up work

Use exact-revision history from the frontend approval and plan detail surfaces.
Later apply, health, recovery, and teardown statuses require their own backend
operations and verified evidence.
