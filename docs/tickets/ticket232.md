# ticket232 — Add commercial launch readiness contract

PR: [#232](https://github.com/Bepoadewale/davdeploy/pull/232)

Branch: `feat/commercial-launch-readiness`

## Problem / goal

Expose the customer onboarding, support, entitlement and billing-provider
boundaries that must accompany automatic infrastructure plans.

## Current repo state

The product has workspace subscription records and support workflows, but plan
results do not present a typed commercial-readiness boundary.

## Research / references used

- `docs/product/automatic-infrastructure-program.md`
- Existing subscription and support contracts.

## Work planned for the PR

- Add typed commercial readiness to composed plans.

## Acceptance criteria

- [x] Onboarding and support boundaries are explicit.
- [x] Entitlements remain separate from payment collection.
- [x] Focused validation passes.

## Acceptance status

Implementation and focused validation are complete.

## Tests / validation performed

Recorded in `docs/test/test232.md`.

## Evidence files produced

`docs/test/test232.md`

## Boundaries

This PR does not configure a payment provider or claim payment collection is live.

## Follow-up work

Configure and validate a billing provider separately when commercial payment
collection is authorised.
