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
- Verify that the exact revision belongs to the authenticated organization
  and requested project before querying runs.
- Bind both returned items and cursor anchors to the same revision filter.
- Test exact matches, invalid/foreign revision denial, and cursor isolation.
- Keep the endpoint read-only and preserve all execution gates.

## Acceptance criteria

- [ ] An authorized customer can request history for one exact revision.
- [ ] A revision from another project or tenant cannot be queried or used as
      a cursor scope.
- [ ] Pagination remains deterministic and bound to the selected revision.
- [ ] Existing project-wide history behavior remains unchanged when the
      filter is omitted.
- [ ] No approval, apply, health, recovery, or teardown capability is added.

## Acceptance status

Pending implementation and validation.

## Tests / validation performed

Pending implementation. Focused tests, `make verify`, OpenAPI checks,
documentation conventions, diff checks, clean-room validation, and current-head
GitHub checks will be recorded here.

## Evidence files produced

- `docs/test/test334.md` will record the local-only implementation boundary.

## Boundaries

No AWS, Bedrock, CodeBuild, state API, or customer workload calls are needed.
This does not make plans approvable or enable deployment.

## Follow-up work

Use exact-revision history from the frontend approval and plan detail surfaces.
Later apply, health, recovery, and teardown statuses require their own backend
operations and verified evidence.
