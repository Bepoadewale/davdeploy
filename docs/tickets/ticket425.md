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
- Pass the same validated range through both Terraform-hosted runtime roots and
  document the local environment setting. Existing per-call timeout and
  output-token limits remain in force, with at most three structured requests.
- Retry only schema-invalid Nova responses. Each repair receives bounded
  validation locations/types and the prior response as untrusted data; local
  Pydantic validation remains authoritative.
- Preserve usage/evidence aggregation across all model calls and make failure
  messages report the configured bound without exposing response contents.
- Keep fixture behavior, model/provider selection, feature flags, hosted state,
  and all infrastructure execution paths unchanged.

## Acceptance criteria

- [x] Default behavior still makes at most one schema-repair call.
- [x] Zero disables schema repair; the invalid response fails closed.
- [x] A configured limit of two allows a second correction and succeeds only
  when the final response passes the local schema.
- [x] Invalid setting values fail during provider construction; no unbounded
  retry is possible.
- [x] Call count, token, timeout, and usage evidence stay bounded and accurate.
- [x] Focused tests (22), full verification (1,303), documentation conventions,
  Terraform formatting/validation, and diff checks pass.
- [x] All seven required CI checks pass on implementation source head `dbb6b13` in
  [run `44182459869`](https://github.com/Bepoadewale/davdeploy/actions/runs/44182459869).

## Acceptance status

Implementation is complete locally. Focused and full verification, Terraform
formatting/validation for both changed roots, and documentation checks passed.
All seven required checks passed on source head `dbb6b13` in run `44182459869`.
The final evidence commit will be documentation-only; its fresh-head CI result
will be recorded in the PR description.

## Tests / validation performed

Focused and full verification, Terraform formatting and validation for both
changed runtime roots, documentation conventions, and diff checks passed.
All seven required CI jobs passed on implementation source head `dbb6b13` in
run `44182459869`. The documentation-only evidence commit's fresh-head CI
result will be recorded in the PR description.

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
