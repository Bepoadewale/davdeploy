# ticket203 - Targeted API rate limits and security alerts

PR: [#203](https://github.com/Bepoadewale/davdeploy/pull/203)
Branch: `feat/targeted-rate-limits`

## Problem / goal

Strengthen abuse resistance for sensitive DavDeploy API actions and notify operators about repeated authorization, throttling, and Cognito sign-in failures.

## Current repo state

The hosted HTTP API has a broad stage limit of 25 requests per second with a burst of 50. The
application-level limiter defaults to disabled unless an environment value is set. Existing alarms
cover Lambda failures, API 5xx responses, worker failures, DLQ messages, and Aurora capacity, but
not repeated 401, 403, 429, or Cognito sign-in failures.

## Research / references used

AWS API Gateway HTTP API route-level throttling documentation; AWS Cognito CloudWatch metrics for
`SignInSuccesses` and `SignInThrottles`; current serverless Terraform and API middleware.

## Work planned for the PR

1. Set a non-zero per-runtime fallback limit in the hosted Lambda environment.
2. Add API Gateway route limits for invitation, plan, AWS verification, support, and API credential actions.
3. Enable privacy-minimal API Gateway access logs with request ID, route key, status, and integration error only.
4. Turn 401, 403, and 429 log events into CloudWatch metrics and burst alarms.
5. Add Cognito failed-sign-in and sign-in-throttle alarms.
6. Add implementation and Terraform contract tests plus the operator response guidance.

## Acceptance criteria

- [x] Sensitive API routes have lower Gateway limits before application work begins.
- [x] Hosted Lambda has a non-zero fallback limiter.
- [x] Repeated API 401, 403, and 429 responses alarm through the operations topic.
- [x] Repeated Cognito sign-in failures and sign-in throttles alarm through the operations topic.
- [x] Logs omit source IP, authorization headers, credentials, one-time codes, and request bodies.
- [x] Tests cover the safe local 429 response and Terraform contracts.

## Acceptance status

Implemented and locally validated; pending CI, review, and a separately authorised Terraform apply.

## Tests / validation performed

Recorded in `docs/test/test203.md`.

## Evidence files produced

`docs/test/test203.md`.

## Boundaries

This PR changes control-plane rate limits, CloudWatch logs, metric filters, and alarms. It does not
modify customer cloud resources, enable customer workload execution, store credentials, inspect
customer traffic content, or introduce a WAF.

## Follow-up work

After a reviewed apply, confirm the deployed stage route settings, access-log delivery, alarm state,
and notification delivery. An API edge/WAF design and administrator MFA remain separate work.
