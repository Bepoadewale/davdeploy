# ticket158 — Permit App Runner service runtime-role pass-through

PR: Pending
Branch: `fix/app-runner-runtime-passrole-condition`

## Problem / goal

The bounded customer role could not pass its scoped runtime role during App Runner service creation.

## Current repo state

The service plan and immutable image are valid, but AWS denied `iam:PassRole` for the runtime role.

## Research / references used

- Failed bounded CodeBuild runner log for the reviewed App Runner service plan.
- Customer connection CloudFormation role policy.

## Work planned for the PR

- Add only `apprunner.amazonaws.com` to the existing scoped `iam:PassedToService` condition.

## Acceptance criteria

- [ ] The customer execution role can pass only its connection-scoped roles to App Runner.
- [ ] CloudFormation template validation and CI pass.

## Acceptance status

Implementation pending validation.

## Tests / validation performed

- Pending CloudFormation template validation.

## Evidence files produced

- `docs/test/test158.md`

## Boundaries

No deletion permission is added.

## Follow-up work

Update the customer connection stack and rerun the reviewed service apply.
