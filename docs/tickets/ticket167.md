# ticket167 — Define customer beta readiness boundary

PR: [#167](https://github.com/Bepoadewale/davdeploy/pull/167)
Branch: `docs/customer-beta-readiness`

## Problem / goal

Make the hosted control-plane evidence and customer-beta boundary accurate, actionable, and safe for operator-led onboarding.

## Current repo state

The AWS-hosted runtime is operating with Cognito, API Gateway, Lambda, Aurora PostgreSQL, and a
Cloudflare-hosted browser client. Existing status text incorrectly stated that the RDS contract had
not been applied, while other product capabilities remain intentionally unexecuted.

## Research / references used

- Deployed AWS runtime inventory and API health check.
- Cloudflare Pages production configuration and custom-domain inspection.
- Cognito identity/client configuration and exact-origin API CORS inspection.

## Work planned for the PR

- Correct the hosted persistence statement.
- Record the operator-led customer-beta boundary and cost-safe invitation constraint.

## Acceptance criteria

- [x] Correct hosted persistence status without overstating workload-execution evidence.
- [x] Document customer entry criteria, operational beta workflow, and unavailable capabilities.
- [x] Preserve the boundary that approval and planning are not deployment.

## Acceptance status

All acceptance criteria are met.

## Tests / validation performed

Documentation-only change. Runtime evidence is not required. Reviewed against the current deployed
runtime inventory, Cloudflare Pages configuration, Cognito configuration, and API health endpoint.

## Evidence files produced

No `docs/test/test167.md` file is required because this PR changes documentation only and does not
perform a customer workload test run.

## Boundaries

This PR does not change application configuration, identity, AWS resources, DNS, Cloudflare, or
email delivery.

## Follow-up work

Configure tested invitation delivery after an owner-approved email cost decision, run a controlled
browser acceptance journey, and separately enable any customer execution capability only through
its own approved delivery plan.
