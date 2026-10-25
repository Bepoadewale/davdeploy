# ticket168 — Cache bounded AWS pricing evidence

PR: [#168](https://github.com/Bepoadewale/davdeploy/pull/168)
Branch: `feat/cost-evidence-cache`

## Problem / goal

Avoid repeatedly charging Cost Explorer for identical customer discovery evidence while preserving
timestamped, customer-account-scoped pricing limitations.

## Current repo state

Each AWS discovery invoked Cost Explorer even when the account and region had already been queried
recently. Cost Explorer charges per request.

## Research / references used

- Current account Cost Explorer usage and pricing evidence adapter.
- Existing customer-cloud lifecycle tests.

## Work planned for the PR

- Cache bounded pricing evidence by customer account and region.
- Surface cache state and bounded freshness duration.
- Add regression coverage proving repeated discovery avoids a second Cost Explorer call.

## Acceptance criteria

- [x] Cache entries cannot cross customer-account or region boundaries.
- [x] Default TTL is bounded and configurable without accepting unsafe values.
- [x] Evidence states whether it was a cache hit or miss.
- [x] Regression tests pass.

## Acceptance status

Implementation and focused validation are complete; full verification is recorded before review.

## Tests / validation performed

See `docs/test/test168.md`.

## Evidence files produced

- `docs/test/test168.md`

## Boundaries

This is an in-process cache for read-only pricing evidence. It does not cache credentials, expose
Cost Explorer data to a browser, change a customer account, or make pricing authoritative.

## Follow-up work

Add durable, explicitly invalidated caching only if real customer usage justifies it.
