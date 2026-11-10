# ticket333 — tenant-scoped Nova plan history

PR: [#333](https://github.com/Bepoadewale/davdeploy/pull/333)
Branch: `feat/generated-plan-history-333`
Base: `main`

## Problem / goal

Let an authorized customer find earlier Nova plan runs for a project and
check their latest safe status without already knowing a run ID. Add a
read-only, bounded, paginated API over durable generated plan runs. This slice
does not add apply, pricing, health, recovery, or destroy behavior.

## Current repo state

- Backend `main` includes tenant-isolated Terraform state and the opt-in
  remote-state worker path through PRs #331 and #332. Both remain disabled by
  default and are not deployed.
- `GET /api/v1/generated-plan-runs/{run_id}` returns safe status for one run,
  but there is no history/list route. The route enforces organization scope
  and limits non-administrators to their own requests.
- Run status is currently planning-only. A ready result is
  `PLAN_READY_REVIEW_ONLY`; it cannot apply or destroy resources.

## Research / references used

- Existing tenant authorization and safe projection:
  `ProductService.generated_plan_run_detail()` and
  `ProductService._generated_plan_run_payload()`.
- Existing durable run model and tenant/revision indexes:
  `GeneratedPlanRun` in `apps/api/src/davdeploy/models.py`.
- Existing route conventions in `apps/api/src/davdeploy/main.py`.

## Work planned for the PR

- Add a project-scoped history endpoint using the authenticated organization.
- Include the customer-facing plan title and revision number in each history
  entry so customers can distinguish plans without decoding identifiers.
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

- [x] Authorized users can page through their project plan history without
      already knowing a run ID.
- [x] Workspace administrators can view runs for their organization and
      project; other users see only their own runs.
- [x] Foreign-tenant, foreign-project, and foreign-requester records cannot
      be disclosed through results or cursor behavior.
- [x] Ordering and pagination are deterministic, bounded, and tested.
- [x] Responses contain only the established customer-safe status projection,
      with the plan title and revision number needed to identify each entry.
- [x] No mutation, apply, approval, or teardown capability is introduced.

## Acceptance status

The API and service behavior are implemented and locally tested. Focused and
full verification, OpenAPI checks, and the isolated clean-room cycle passed.
Current-head GitHub CI and review are pending. No hosted state or workload
execution is claimed.

## Tests / validation performed

- `uv run pytest tests/test_nova_plan_runs.py -q`: 40 passed.
- `uv run ruff check apps/api/src/davdeploy/main.py apps/api/src/davdeploy/service.py tests/test_nova_plan_runs.py`: passed after import formatting.
- `make openapi-update` regenerated `contracts/openapi-v1.json`; `make openapi-check` passed.
- Full `make verify`: 865 passed; Ruff, Actions configuration, OpenAPI, and Docker Compose configuration passed.
- Fresh isolated `make local-proof` passed on `e046917`; all 865 tests, API contract, customer-plan E2E, trace check, and cleanup passed. Exact resources and cleanup evidence are in `docs/test/test333.md`.
- Documentation convention validation and `git diff --check` passed.
- Runtime and API evidence: `docs/test/test333.md`.

## Evidence files produced

- `docs/test/test333.md` records local tests and the no-AWS boundary.

## Boundaries

No AWS, Bedrock, CodeBuild, state API, or customer workload calls are needed.
Remote state, pricing, exact-plan approval, apply, health, recovery, and
teardown remain separate unmet gates.

## Follow-up work

Bind the customer plan-history view to this API. Add lifecycle status and
history events only when the corresponding backend operations exist and emit
verified evidence.
