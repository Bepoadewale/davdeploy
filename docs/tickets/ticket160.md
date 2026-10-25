# ticket160 — Use an App Runner-valid service name

PR: Pending
Branch: `fix/app-runner-service-name`

## Problem / goal

The connection-scoped foundation name exceeds App Runner's 40-character service-name limit.

## Current repo state

The validated service plan reaches AWS but App Runner rejects the long service name.

## Research / references used

- Bounded service-apply runner error from App Runner.

## Work planned for the PR

- Use a short, connection-prefix-scoped App Runner service name while retaining existing foundation names.

## Acceptance criteria

- [ ] The App Runner service name is at most 40 characters.
- [ ] Foundation resource names remain unchanged.
- [ ] Tests and CI pass.

## Acceptance status

Implementation and local validation complete; CI pending.

## Tests / validation performed

- Ruff and focused cloud-execution tests.

## Evidence files produced

- `docs/test/test160.md`

## Boundaries

No deletion behavior changes.

## Follow-up work

Deploy the correction and run a fresh reviewed service plan.
