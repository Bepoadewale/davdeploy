# ticket161 — Enable customer-approved administrator execution and retain foundation names

PR: Pending
Branch: `feat/admin-execution-role-capability`

## Problem / goal

The customer selected an administrator execution model for broad AWS architecture support. The
App Runner service also needs a short name without replacing its existing foundation log group.

## Current repo state

The execution role is already isolated from discovery, external-ID protected, short-lived, and used
only by approved immutable plans. Its policy is profile-specific; the customer requested a dedicated
AdministratorAccess role. The service-name adjustment would otherwise rename the log group.

## Research / references used

- Customer decision to use a dedicated administrator execution role.
- Guarded App Runner plan evidence and AWS service-name constraints.

## Work planned for the PR

- Attach AdministratorAccess only to the separate customer execution role.
- Keep discovery read-only and preserve review, audit, region, account, plan, and destroy guards.
- Separate the short App Runner name from the retained foundation/log-group name.

## Acceptance criteria

- [ ] Discovery remains separate and read-only.
- [ ] The execution role requires broker trust plus the connection external ID.
- [ ] The service plan does not replace the existing log group merely to use a short service name.
- [ ] Tests and CI pass.

## Acceptance status

Implementation and focused validation pending.

## Tests / validation performed

- Pending focused tests, template validation, and CI.

## Evidence files produced

- `docs/test/test161.md`

## Boundaries

AdministratorAccess is customer-approved and attached only to the dedicated execution role. The
product still requires immutable approved plans and explicit destroy confirmation.

## Follow-up work

Update the existing connection stack, regenerate the service plan, apply, observe, and then run the
customer-authorized governed destroy.
