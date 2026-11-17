# ticket426 — record validated Nova intent proposal identity

PR: https://github.com/Bepoadewale/davdeploy/pull/426
Branch: `feat/nova-proposal-digest-426`

## Problem / goal

Nova model metadata already records its provider, model, prompt version, input
digest, usage, and call evidence. It does not identify the locally validated
proposal that the service accepted after any repair attempts. Package 3 of the
Nova goal requires model, prompt, context, and proposal versions/digests.

## Current repo state

Backend `main` is `df46439a613638330b5b0925af2081d7acda2de3`, including merged
PR #425. PR #399 remains open and draft; this change does not depend on enabling
its apply path.

## Research / references used

- `apps/api/src/davdeploy/intent.py`
- `apps/api/src/davdeploy/model_gateway.py`
- `apps/api/src/davdeploy/domain.py`
- `apps/api/src/davdeploy/service.py`
- `tests/test_nova_intent.py`
- `DAVDEPLOY_NOVA_GOAL.md`, package 3: record model, prompt, context, and
  proposal versions/digests

## Work planned for the PR

- Assign an explicit version to the strict `NovaIntentProposal` contract.
- Hash the final locally validated proposal using the existing canonical model
  input digest helper and include its version/digest in model metadata.
- Ensure a repaired response records the accepted proposal, not the invalid
  response that preceded it.
- Keep fixture metadata distinct and do not retain raw output in new fields.

## Scope

- This changes source metadata only; existing model output and API behavior
  remain unchanged.
- Proposal digest is over the validated, normalized local model representation.
- Do not include raw proposal text, credentials, or new customer content in the
  metadata beyond fields already carried by the validated proposal.
- No Bedrock or AWS calls, Terraform actions, feature-gate changes, or hosted
  deployment are included.

## Acceptance criteria

- [x] Accepted Nova responses include proposal version and stable digest.
- [x] A repair sequence hashes the final validated proposal.
- [x] Equivalent normalized proposals have the same digest; a changed field
  changes the digest.
- [x] Out-of-scope Nova responses have the same proposal identity evidence.
- [x] Fixture behavior does not claim Nova proposal provenance.
- [x] Focused tests (23), full verification (1,304), docs conventions, and diff
  checks pass.
- [x] All seven required CI checks pass on implementation head `e2f98fe` in
  [run `44185396711`](https://github.com/Bepoadewale/davdeploy/actions/runs/44185396711).

## Acceptance status

Implementation is complete. Focused/full verification and documentation checks
passed locally; all seven required CI checks passed on implementation head
`e2f98fe` in run `44185396711`.

## Tests / validation performed

Focused tests and full verification passed locally. Final run details are in
`docs/test/test426.md`; the documentation commit's CI result will be recorded
in the PR description.

## Evidence files produced

- `docs/tickets/ticket426.md`
- `docs/test/test426.md`

## Boundaries

No model call, AWS operation, Terraform plan/apply, hosted runtime change,
credential issuance, or customer workload is part of this package.

## Follow-up work

This digest records proposal identity but does not prove repeatability,
correctness, or hosted deployment behavior. Package 3's schema/document
provenance, real Nova evaluation, and remaining acceptance gates are separate.
