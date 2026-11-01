# ticket225 — Infer customer capabilities from intent and evidence

PR: [#225](https://github.com/Bepoadewale/davdeploy/pull/225)

Branch: `feat/intent-capability-intelligence`

## Problem / goal

Let customers describe a product normally while DavDeploy infers an
allow-listed capability vocabulary for the composed architecture plan. Existing
repository evidence augments that result; neither source asks the customer to
select AWS services.

## Current repo state

PR #224 introduced the internal composed-module graph. Intent extraction has
a deterministic fixture and an optional guarded Bedrock Nova path, but neither
populates the graph's capability vocabulary.

## Research / references used

- [Automatic infrastructure programme](../product/automatic-infrastructure-program.md)
- [Composed-plan foundation ticket](ticket224.md)
- Existing structured model boundary in `apps/api/src/davdeploy/intent.py`

## Work planned for the PR

- Extend structured Bedrock and deterministic intent extraction with safe
  customer capability inference.
- Drop unknown/model-invented capabilities locally.
- Merge safe repository signals into the same capability set.
- Preserve existing material business-constraint questions.

## Acceptance criteria

- [x] Customers still never choose an AWS service.
- [x] Bedrock output is locally allow-listed before planning uses it.
- [x] Deterministic fallback recognises common product needs.
- [x] Repository hints can enrich the capability set.
- [x] Focused validation passes.

## Acceptance status

Implementation and focused validation are complete.

## Tests / validation performed

Recorded in `docs/test/test225.md`.

## Evidence files produced

`docs/test/test225.md`

## Boundaries

This PR does not allow Bedrock, a repository, or a browser to choose AWS
resources, cloud permissions or execution commands. The capability vocabulary
is an input to deterministic composition only.

## Follow-up work

PR #226 supplies universal modules; #227 adds data/asynchronous modules;
#228 adds execution implementations; #229–#232 retain the programme sequence
recorded in `docs/product/automatic-infrastructure-program.md`.
