# ticket346 — paginated customer plan revision history

PR: pending
Branch: `feat/customer-plan-revision-history-346`
Base: `main`

## Goal

Let an authorized project member retrieve all customer plan revisions through a bounded, tenant-scoped cursor API. The dashboard currently returns only its newest 20 revisions. This endpoint complements the existing paginated Nova run-status API; it does not add apply, approval, pricing, health, recovery, or teardown behavior.

## Current repository state

- `GET /api/v1/dashboard` limits plan revisions to 20.
- `GET /api/v1/projects/{project_id}/generated-plan-runs` pages Nova run status, but does not list revisions with no Nova run.
- Revision detail is available by exact ID and validates organization/project ownership.

## Research / references

- `ProductService.workspace_dashboard()` and revision detail authorization in `service.py`.
- Existing cursor and visibility conventions in `generated_plan_run_history()`.
- Existing customer plan detail endpoint and dashboard projection.

## Planned work

- Add a read-only project-scoped plan-revision history endpoint with stable cursor pagination and a bounded page size.
- Preserve workspace-administrator and plan-creator visibility; authorize cursor anchors under the same project and visibility rules.
- Return only customer-safe plan summary fields and avoid exposing internal subjects or plan content.
- Add service/route tests and update OpenAPI plus PR evidence.

## Acceptance criteria

- [ ] Authorized customers can page through all visible revisions in deterministic order.
- [ ] Cross-tenant, cross-project, and invisible creator records/cursors are denied without disclosure.
- [ ] Invalid cursors and page limits fail safely; response contains no private plan content.
- [ ] Focused and full required verification pass; PR checks pass.
- [ ] No AWS calls or customer infrastructure mutations are made.

## Boundaries and follow-up

This improves history discoverability only. Nova saved-plan pricing/approval, hosted apply, health, recovery, and destroy remain separate unmet gates. Frontend integration may consume this endpoint in a later focused PR.
