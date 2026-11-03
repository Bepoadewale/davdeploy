# ticket268 — Real serverless API renderer certification

PR: pending

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

Add a disposable certification root and evidence covering deployment, HTTP
response, and destruction through the Terraform run monitor.

## Acceptance criteria

- [ ] Disposable Lambda and HTTP API deploy in the controlled AWS account.
- [ ] HTTP endpoint returns the expected test response.
- [ ] All test resources are destroyed and absence verified.
- [ ] Focused checks and required CI pass.

## Acceptance status

In progress.

## Tests / validation performed

Pending AWS certification.

## Evidence files produced

Pending `docs/test/test268.md`.

## Boundaries

Only resources tagged for this disposable test are created. No customer data
or production account is used.

## Follow-up work

Add saved-plan binding and integrate the renderer with CodeBuild dispatcher
before making it available to customer execution.
