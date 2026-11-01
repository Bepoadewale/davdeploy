# ticket222 - administrator customer-review decisions through MCP

PR: [#222](https://github.com/Bepoadewale/davdeploy/pull/222)

## Problem / goal

Allow an authenticated workspace administrator using MCP to record an explicit decision for a submitted customer-plan revision.

## Current repo state

The hosted API already authorizes administrator self-approval and records the decision, exact content digest, actor, and audit event. Browser users can call that endpoint. MCP could create and submit customer reviews but could not call the governed decision endpoint.

## Research / references used

- `decide_customer_plan_revision` in `apps/api/src/davdeploy/main.py`.
- Existing tenant and administrator checks in `ProductService.decide_infrastructure_plan`.
- MCP tool boundary and contract tests in `apps/api/src/davdeploy/mcp.py` and `tests/test_agent_interfaces.py`.

## Work planned for the PR

- Add one MCP tool that forwards only `APPROVED` or `REJECTED`, exact digest, and optional reason.
- Preserve API-side identity, membership, role, state, and digest validation.
- Add a forwarding-contract test.

## Acceptance criteria

- [x] MCP exposes an explicit customer-review decision tool.
- [x] The tool does not mint credentials or bypass API authorization.
- [x] The API remains the authority for administrator role and tenant checks.
- [ ] Hosted administrator MCP acceptance is recorded after deployment.

## Acceptance status

Implementation is complete locally. Hosted deployment and administrator MCP acceptance remain pending.

## Tests / validation performed

See `docs/test/test222.md`.

## Evidence files produced

`docs/test/test222.md`

## Boundaries

This does not grant MCP cloud credentials or arbitrary execution. It exposes only the existing explicit customer-review decision endpoint. The identity token must resolve to a workspace administrator, and the API persists the decision against the immutable submitted digest.

## Follow-up work

Build and validate an ECS execution adapter separately. The current hosted executor is App Runner-only and the AWS account currently rejects new App Runner services.
