# ticket351 — Expose Nova plan-role setup readiness

PR: [#351](https://github.com/Bepoadewale/davdeploy/pull/351) (draft)
Branch: `feat/nova-plan-role-setup-status-351`
Base: `main`

## Problem / goal

Expose whether a verified, discovery-only AWS connection can safely start the separate Nova plan-role setup flow. The response must reflect the plan-role feature gate and required setup configuration without exposing credentials or enabling planning.

## Current repo state

The API already generates a plan-only Quick Create link for workspace administrators when Nova plan-role verification is enabled. The customer connection list returns plan-role state but does not say whether setup is currently available. The frontend therefore cannot show a truthful setup action.

## Research / references used

- `ProductService.aws_quick_create_setup()` and `ProductService.plan_role_policy_status()`
- `GET /api/v1/cloud-connections` in `apps/api/src/davdeploy/main.py`
- `docs/tickets/ticket326.md`, `docs/tickets/ticket340.md`, and `docs/tickets/ticket348.md`

## Work planned for the PR

- Add a customer-safe, derived `plan_role_setup_available` value to each cloud connection summary.
- Return true only for a verified AWS discovery-only connection with no execution or plan role, with role verification enabled and the required discovery broker/template configuration present.
- Keep endpoint authorization and `aws_quick_create_setup()` server-side checks authoritative; this field is a display hint only.
- Add positive and negative route/service tests and update API contract documentation as required.
- Do not enable any runtime feature flag or create AWS resources.

## Acceptance criteria

- [x] Setup availability is true only when every server-side prerequisite is present.
- [x] Existing execution roles, unverified connections, configured plan roles, and disabled/missing setup gates yield false.
- [x] Cross-tenant access remains denied; the availability field exposes no secrets or role credentials.
- [x] The setup endpoint remains authoritative and no planning or AWS mutation is enabled by this PR.
- [ ] Focused tests, full verification, documentation conventions, and required GitHub CI pass.

## Acceptance status

The customer-safe readiness signal and fail-closed tests are implemented. Focused and full local verification passed; required GitHub CI and current-head review remain.

## Tests / validation performed

- `GITHUB_PR_NUMBER=351 python scripts/check_doc_conventions.py` — passed.
- `uv run ruff check apps/api/src/davdeploy/main.py apps/api/src/davdeploy/service.py tests/test_connection_experience.py` — passed.
- `uv run pytest tests/test_connection_experience.py -q` — 16 passed; one existing Starlette/httpx deprecation warning.
- `DAVDEPLOY_DATABASE_URL=sqlite+pysqlite:///:memory: make verify` — 904 tests passed; Actions configuration, Ruff, OpenAPI snapshot, and Docker Compose configuration passed. The existing Starlette/httpx deprecation warning remains.
- No AWS calls, plan-role setup, infrastructure changes, or customer workload were used.

## Evidence files produced

- No customer-workload evidence is applicable; this PR will not call AWS or mutate infrastructure.

## Boundaries

This PR only describes whether role setup can be offered. It does not attest effective customer permissions, enable the plan runner, generate a Terraform plan, approve a plan, or apply infrastructure.

## Follow-up work

Merge/deploy the administrator-only Connections-page setup flow from frontend PR #102 together with this readiness field. Keep plan-role setup unavailable until the runtime gate and required setup configuration are deliberately enabled and verified.
