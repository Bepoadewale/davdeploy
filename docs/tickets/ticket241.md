# ticket241 — Events module batch reopen

PR: [#241](https://github.com/Bepoadewale/davdeploy/pull/241)

Branch: `feat/module-batch-04-events`

## Problem / goal

Merge the event-service module batch after GitHub closed dependent draft #236.

## Current repo state

Data batch #240 is merged. This PR supersedes closed #236.

## Research / references used

AWS Terraform provider schemas and recorded disposable lifecycle evidence.

## Work planned for the PR

Merge SQS, EventBridge, Step Functions, SNS and SES module roots.

## Acceptance criteria

- [x] Event module roots exist and remain disabled.
- [x] Disposable SQS, EventBridge and SNS lifecycle evidence exists.

## Acceptance status

Ready for CI.

## Tests / validation performed

See `docs/test/test241.md` and source evidence `docs/test/test236.md`.

## Evidence files produced

`docs/test/test241.md`

## Boundaries

SES DNS verification and workflow-specific Step Functions validation remain
separate. No customer execution is enabled.

## Follow-up work

Validate customer-approved workflow roles and controlled mail domains.
