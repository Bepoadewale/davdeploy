# ticket167 — Define customer beta readiness boundary

PR: [#167](https://github.com/Bepoadewale/davdeploy/pull/167)

## Goal

Make the hosted control-plane evidence and customer-beta boundary accurate, actionable, and safe for operator-led onboarding.

## Current state

The AWS-hosted runtime is operating with Cognito, API Gateway, Lambda, Aurora PostgreSQL, and a
Cloudflare-hosted browser client. Existing status text incorrectly stated that the RDS contract had
not been applied, while other product capabilities remain intentionally unexecuted.

## Acceptance criteria

- [x] Correct hosted persistence status without overstating workload-execution evidence.
- [x] Document customer entry criteria, operational beta workflow, and unavailable capabilities.
- [x] Preserve the boundary that approval and planning are not deployment.

## Validation

Documentation-only change. Runtime evidence is not required. Reviewed against the current deployed
runtime inventory, Cloudflare Pages configuration, Cognito configuration, and API health endpoint.

## Follow-up

Configure tested invitation delivery, run a controlled browser acceptance journey, and separately
enable any customer execution capability only through its own approved delivery plan.
