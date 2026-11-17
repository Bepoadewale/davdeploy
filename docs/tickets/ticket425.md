# ticket425 — bound and configure Nova intent schema repair

PR: https://github.com/Bepoadewale/davdeploy/pull/425
Branch: `feat/nova-bounded-repair-425`

## Problem / goal

Nova intent extraction currently makes exactly one hard-coded repair call when
the structured response fails local schema validation. Package 3 of
`DAVDEPLOY_NOVA_GOAL.md` requires explicit, bounded model-attempt, time, and
output budgets. The existing model gateway already bounds each structured call
by configured timeout and output-token limits, but the intent repair count
cannot be configured or set to zero.

## Current repo state

Backend `main` is `602206ee1fd73b4582015ec30d2b5e472d72baf7`. PR #399 remains
open and draft for the separate exact-plan apply boundary. This package changes
only bounded Nova intent extraction and does not depend on enabling that path.

## Research / references used

- `apps/api/src/davdeploy/intent.py`
- `apps/api/src/davdeploy/model_gateway.py`
- `tests/test_nova_intent.py`
- `DAVDEPLOY_NOVA_GOAL.md`, package 3: evidence and bounded repair loop

## Work planned for the PR

- Make schema-repair attempts explicitly configurable with a safe hard ceiling.
- Preserve validation-only retry inputs and aggregate model usage/evidence.
- Add focused positive, negative, and configuration-boundary tests.

## Scope

- Add a bounded `DAVDEPLOY_INTENT_SCHEMA_REPAIR_ATTEMPTS` setting, defaulting to
  one and accepting only values from zero through two.
- Retry only schema-invalid Nova responses. Each repair receives bounded
  validation locations/types and the prior response as untrusted data; local
  Pydantic validation remains authoritative.
- Preserve usage/evidence aggregation across all model calls and make failure
  messages report the configured bound without exposing response contents.
- Keep fixture behavior, model/provider selection, feature flags, hosted state,
  and all infrastructure execution paths unchanged.

## Acceptance criteria

- [ ] Default behavior still makes at most one schema-repair call.
- [ ] Zero disables schema repair; the invalid response fails closed.
- [ ] A configured limit of two allows a second correction and succeeds only
  when the final response passes the local schema.
- [ ] Invalid setting values fail during provider construction; no unbounded
  retry is possible.
- [ ] Call count, token, timeout, and usage evidence stay bounded and accurate.
- [ ] Focused tests, full verification, documentation conventions, and diff
  checks pass.
- [ ] All seven required CI checks pass on the final PR head.

## Acceptance status

Not implemented yet. Ticket and evidence files are being established before
source changes.

## Tests / validation performed

Before implementation, only documentation convention and diff checks will be
run. Full checks will be recorded after the source change.

## Evidence files produced

- `docs/tickets/ticket425.md`
- `docs/test/test425.md`

## Boundaries

This is source/test work only. It does not make model tools executable, issue
credentials, create plans, change AWS or hosted control-plane state, or prove
customer infrastructure behavior.

## Follow-up work

This package does not implement the rest of package 3 (schema provenance,
repository/document retrieval, real Nova repeatability evaluation, or a full
model-correction conversation). Those gates remain separately tracked.
