# ticket333 — tenant-scoped Nova plan history

## Goal

Let an authorized customer find earlier Nova plan runs for a project and
check their latest safe status without already knowing a run ID. Add a
read-only, bounded, paginated API over durable generated plan runs. This slice
does not add apply, pricing, health, recovery, or destroy behavior.

## Current repository state

- Backend `main` includes tenant-isolated Terraform state and the opt-in
  remote-state worker path through PRs #331 and #332. Both remain disabled by
  default and are not deployed.
- `GET /api/v1/generated-plan-runs/{run_id}` returns safe status for one run,
  but there is no history/list route. The route enforces organization scope
  and limits non-administrators to their own requests.
- Run status is currently planning-only. A ready result is
  `PLAN_READY_REVIEW_ONLY`; it cannot apply or destroy resources.

## Research and references

- Existing tenant authorization and safe projection:
  `ProductService.generated_plan_run_detail()` and
  `ProductService._generated_plan_run_payload()`.
- Existing durable run model and tenant/revision indexes:
  `GeneratedPlanRun` in `apps/api/src/davdeploy/models.py`.
- Existing route conventions in `apps/api/src/davdeploy/main.py`.

## Work planned

- Add a project-scoped history endpoint using the authenticated organization.
- Reuse existing requester/admin visibility rules and safe status projection.
- Add a hard-bounded page size and stable cursor pagination using an
  organization/project/requester-authorized prior run as the cursor anchor.
- Return no runner credentials, build identifiers, object keys/versions,
  Terraform state, saved-plan bytes, or raw result metadata.
- Add route and service tests for ordering, pagination, limits, requester
  visibility, administrator visibility, cross-project/tenant denial, invalid
  cursors, and safe response shape.
- Keep the endpoint read-only; do not change execution or approval gates.

## Acceptance criteria

- [ ] Authorized users can page through their project plan history without
      already knowing a run ID.
- [ ] Workspace administrators can view runs for their organization and
      project; other users see only their own runs.
- [ ] Foreign-tenant, foreign-project, and foreign-requester records cannot
      be disclosed through results or cursor behavior.
- [ ] Ordering and pagination are deterministic, bounded, and tested.
- [ ] Responses contain only the established customer-safe status projection.
- [ ] No mutation, apply, approval, or teardown capability is introduced.

## Validation and evidence

Pending implementation. Focused tests, full `make verify`, OpenAPI snapshot,
documentation conventions, diff checks, and current-head GitHub CI will be
recorded here. Evidence file: `docs/test/test333.md`.

## Boundaries

No AWS, Bedrock, CodeBuild, state API, or customer workload calls are needed.
Remote state, pricing, exact-plan approval, apply, health, recovery, and
teardown remain separate unmet gates.

## Follow-up

Bind the customer plan-history view to this API. Add lifecycle status and
history events only when the corresponding backend operations exist and emit
verified evidence.
