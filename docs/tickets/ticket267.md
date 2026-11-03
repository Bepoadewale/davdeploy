# ticket267 — Serverless API customer renderer

PR: pending

Branch: `feat/serverless-api-renderer`

## Problem / goal

Add the first non-App-Runner customer workload renderer: a bounded Lambda and
HTTP API deployment with immutable artifact input, health evidence and exact
destroy verification.

## Current repo state

Reusable Lambda and API Gateway modules exist, but no customer workload root
or runner maps the typed `aws-serverless-api` module to them.

## Research / references used

Existing Lambda/API Gateway Terraform modules and the customer App Runner
execution runner contract.

## Work planned for the PR

Create an isolated serverless Terraform root and fixed runner operations for
plan, immutable saved-plan apply, endpoint health check, destroy and absence
verification. Bind the renderer only after its checks pass.

## Acceptance criteria

- [ ] Lambda/API root has scoped tags, role, permission and output contract.
- [ ] Runner accepts only immutable ZIP artifact and approved saved plan.
- [ ] Health and cleanup commands are bounded.
- [ ] Focused tests and full CI pass.

## Acceptance status

In progress.

## Tests / validation performed

Pending implementation.

## Evidence files produced

No real AWS workload is created until a later controlled certification run.

## Boundaries

No arbitrary code path, shell command or IAM policy input is accepted.

## Follow-up work

Perform a disposable real AWS deployment, invoke its endpoint, collect health
evidence and destroy it before enabling customer execution.
