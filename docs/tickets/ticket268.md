# ticket268 — Real serverless API renderer certification

PR: https://github.com/Bepoadewale/davdeploy/pull/268

Branch: `test/real-serverless-api-certification`

## Problem / goal

Certify the customer Lambda and HTTP API renderer with a real disposable AWS
deployment, an HTTP health response and verified cleanup.

## Current repo state

PR #267 added a customer renderer root and fixed runner. The renderer is not
yet connected to the execution registry and has no real customer-shaped
deployment evidence.

## Research / references used

The customer serverless API Terraform root, AWS Lambda/API Gateway modules,
and existing disposable module validation conventions.

## Work planned for the PR

Add a disposable certification root importing the customer serverless API
renderer and using the repository's Lambda test package.

Completed: the renderer was applied in AWS account `654654474502`, region
`us-east-1`; its HTTPS endpoint returned HTTP 200 and `{"ok":true}`. The
monitored destroy completed with 9 resources destroyed. Read-only AWS checks
confirmed the test Lambda, API, and IAM role are absent.

## Acceptance criteria

- [x] Disposable Lambda and HTTP API deploy in the controlled AWS account.
- [x] HTTP endpoint returns the expected test response.
- [x] All 9 Terraform resources are destroyed; Lambda, API, and IAM role absence verified.
- [x] Terraform formatting, initialization, and validation pass.
- [x] Updated PR revision passes required CI (all seven checks passed).

## Acceptance status

Met for the isolated renderer root. This is not evidence of CodeBuild dispatcher
integration or customer execution readiness.

## Tests / validation performed

`terraform fmt -check`, `terraform init`, and `terraform validate` passed for
the validation root. A real HTTPS request returned HTTP 200 with
`{"ok":true}`. Monitored Terraform destroy reported 9 resources destroyed;
read-only AWS lookups returned not-found for the exact test Lambda, HTTP API,
and IAM role. All seven required GitHub CI checks passed on the current PR
revision before this ticket status update.

## Evidence files produced

`docs/test/test268.md`.

## Boundaries

Only resources tagged for this disposable test are created. No customer data
or production account is used.

## Follow-up work

Add immutable saved-plan/artifact binding, integrate this renderer with a
typed CodeBuild dispatcher, then validate the complete hosted customer
lifecycle before enabling customer execution.
