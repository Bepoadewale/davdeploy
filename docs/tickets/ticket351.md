# ticket351 — Expose Nova plan-role setup readiness

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

- [ ] Setup availability is true only when every server-side prerequisite is present.
- [ ] Existing execution roles, unverified connections, configured plan roles, and disabled/missing setup gates yield false.
- [ ] Cross-tenant access remains denied; the availability field exposes no secrets or role credentials.
- [ ] The setup endpoint remains authoritative and no planning or AWS mutation is enabled by this PR.
- [ ] Focused tests, full verification, documentation conventions, and required GitHub CI pass.

## Acceptance status

Implementation has not started. This ticket is the draft-PR bootstrap record.

## Tests / validation performed

- None yet.

## Evidence files produced

- No customer-workload evidence is applicable; this PR will not call AWS or mutate infrastructure.

## Boundaries

This PR only describes whether role setup can be offered. It does not attest effective customer permissions, enable the plan runner, generate a Terraform plan, approve a plan, or apply infrastructure.

## Follow-up work

Expose the administrator-only plan-role setup and verification flow in the customer Connections page; keep it unavailable unless the backend says setup is ready.
