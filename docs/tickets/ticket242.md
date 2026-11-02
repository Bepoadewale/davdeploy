# ticket242 — AI module batch reopen

PR: [#242](https://github.com/Bepoadewale/davdeploy/pull/242)

Branch: `feat/module-batch-05-ai`

## Problem / goal

Merge the AI and batch module root batch after GitHub closed dependent draft #237.

## Current repo state

Events batch #241 is merged. This PR supersedes closed #237.

## Research / references used

AWS Terraform provider schemas and established controlled-execution boundaries.

## Work planned for the PR

Merge Bedrock, knowledge-base, SageMaker, Kinesis and Batch module roots.

## Acceptance criteria

- [x] Five module roots exist and registry entries remain disabled.
- [x] Batch registry identifier is correct.

## Acceptance status

Ready for CI.

## Tests / validation performed

See `docs/test/test242.md` and source record `docs/test/test237.md`.

## Evidence files produced

`docs/test/test242.md`

## Boundaries

No real AI, model, RAG, endpoint, stream or batch workload is enabled.

## Follow-up work

Run controlled service-specific workload and cost validation.
