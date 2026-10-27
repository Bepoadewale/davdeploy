# ticket186 — Make AWS connection setup discovery-only

PR: pending
Branch: `fix/discovery-only-aws-connection-template`

## Problem / goal

Ensure Connect Account creates only a read-only discovery role.

## Current repo state

The former quick-create template also created dormant execution and App Runner roles, including AdministratorAccess.

## Research / references used

- Controlled CloudFormation stack inspection.

## Work planned for the PR

- Remove execution resources and parameters from the customer template and setup link.

## Acceptance criteria

- [x] The template creates only the discovery role.
- [x] It contains no App Runner, pass-role, or AdministratorAccess permission.

## Acceptance status

Locally verified; pending CI and protected template/control-plane deployment.

## Tests / validation performed

Recorded in `docs/test/test186.md`.

## Evidence files produced

- `docs/test/test186.md`

## Boundaries

No execution role or workload is created.

## Follow-up work

Deploy the hosted template and API, then retry the connection.
