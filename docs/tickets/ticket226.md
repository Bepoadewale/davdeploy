# ticket226 — Add universal application module contracts

PR: [#226](https://github.com/Bepoadewale/davdeploy/pull/226)

Branch: `feat/universal-application-modules`

## Problem / goal

Make selected universal modules describe typed resources, controls, observation
and destroy support inside a composed plan without exposing AWS choices to a
customer.

## Current repo state

PRs #224 and #225 produce an internal dependency-ordered module graph from
customer intent and evidence. The graph needs versioned module contracts for
subsequent deployment implementation.

## Research / references used

- [Automatic infrastructure programme](../product/automatic-infrastructure-program.md)
- [Adapter catalogue](../architecture/adapter-catalogue.md)
- Existing guarded App Runner and plan-render contracts.

## Work planned for the PR

- Add typed module contracts to architecture plans.
- Add universal resource/control/observation mappings for edge, web, API,
  application runtime, identity, storage, secrets and operations modules.
- Keep unknown/specialist contracts explicit rather than invented.

## Acceptance criteria

- [x] Universal selected modules have a versioned contract.
- [x] Contracts include resources, policy controls and observation.
- [x] Only the proven App Runner module advertises destroy support.
- [x] Focused validation passes.

## Acceptance status

Implementation and focused validation are complete.

## Tests / validation performed

Recorded in `docs/test/test226.md` before review.

## Evidence files produced

`docs/test/test226.md`

## Boundaries

Plan contracts do not provision resources or widen customer-account IAM.
Execution work remains PR #228.

## Follow-up work

PR #227 adds data/event contracts. PRs #228–#232 continue according to the
programme document.
