# ticket145: Bootstrap App Runner networking service-linked role

PR: #145
Branch: fix/apprunner-networking-prerequisite

## Problem / goal

CreateVpcConnector uses the separate App Runner networking service-linked role,
which trusts `networking.apprunner.amazonaws.com`. The runner only initialized
the general App Runner service-linked role.

## Current repo state

The fresh signed plan succeeded, but its immutable apply safely failed while
creating the VPC connector because AWS could not create
`AWSServiceRoleForAppRunnerNetworking` on behalf of the scoped role.

## Research / references used

- AWS App Runner networking service-linked-role documentation.
- Failed real apply run `408a35c0-6b07-40c4-a763-ca37a4f0127b`.
- `infrastructure/cloudformation/customer-discovery-role.yaml`.

## Work planned for the PR

- Permit only the two required App Runner service-linked role service names.
- Create both roles explicitly and idempotently before an immutable apply.
- Add contract coverage for the networking role.

## Acceptance criteria

- [x] The role policy permits no unrelated service-linked role.
- [x] Runner creation is bounded, idempotent, and occurs after saved-plan verification.
- [x] The App Runner networking prerequisite is represented in static tests.
- [ ] Focused tests and required CI pass.
- [ ] Connection stack, runner release, and fresh live apply pass.

## Acceptance status

Implementation is complete. Validation, CI, customer connection stack update,
guarded runner release, and a fresh live apply remain.

## Tests / validation performed

- Pending shell syntax, policy template validation, focused tests, and documentation convention checks.

## Evidence files produced

- Customer live-run evidence continues in `docs/test/test130.md`.

## Boundaries

- The policy permits only App Runner's general and networking service-linked roles.
- No unrelated IAM role creation is introduced.

## Follow-up work

- Publish the immutable connection template and update the test connection.
- Release the runner and rerun the reviewed customer lifecycle.
