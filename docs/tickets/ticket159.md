# ticket159 — Remove unsupported App Runner pass-role condition

PR: Pending
Branch: `fix/scoped-app-runner-passrole`

## Problem / goal

App Runner `CreateService` does not supply the `iam:PassedToService` context required by the
connection role policy, causing a scoped `iam:PassRole` denial.

## Current repo state

The policy resource list already limits pass-role to the two connection-scoped App Runner roles.
The additional condition prevents service creation.

## Research / references used

- Repeated bounded runner error from App Runner `CreateService`.
- Deployed inline policy inspection.

## Work planned for the PR

- Remove only the unsupported condition; retain the exact two-role resource scope.

## Acceptance criteria

- [ ] App Runner can receive only the connection-scoped ECR and runtime roles.
- [ ] No delete permissions are expanded.
- [ ] Template validation and CI pass.

## Acceptance status

Implementation pending validation.

## Tests / validation performed

- Pending CloudFormation template validation.

## Evidence files produced

- `docs/test/test159.md`

## Boundaries

The policy remains resource-scoped and grants no new resource deletion capability.

## Follow-up work

Update the connection stack, generate a fresh service plan, and retry the reviewed apply.
