# ticket166 — Restore hosted worker Bedrock Nova compatibility

PR: [#166](https://github.com/Bepoadewale/davdeploy/pull/166)
Branch: `fix/worker-bedrock-nova-provider`

## Problem / goal

Restore worker startup for the deployed legacy `bedrock-nova` model-provider value without broadening model access or replaying failed work.

## Current repo state

The hosted worker DLQ contains failed messages because `configured_model_gateway()` rejected `bedrock-nova` before job processing began. Terraform currently emits `bedrock`; the deployed value is a legacy configuration alias.

## Research / references used

- CloudWatch worker error logs identifying the rejected `bedrock-nova` provider.
- Deployed Lambda environment and Terraform runtime configuration.
- Existing model-gateway contract tests.

## Work planned for the PR

- Add only the legacy provider alias required for worker startup.
- Add a regression test and record local validation.

## Acceptance criteria

- [x] The narrow legacy alias resolves to the existing Bedrock Nova gateway.
- [x] Unknown providers remain fail-closed.
- [x] No SQS message is replayed, deleted, or otherwise mutated by this PR.
- [x] Focused regression tests pass.

## Acceptance status

All acceptance criteria are met.

## Tests / validation performed

See `docs/test/test166.md`.

## Evidence files produced

- `docs/test/test166.md`

## Boundaries

Deploy through the reviewed runtime workflow, verify the worker starts, then separately inspect and explicitly authorise any DLQ replay or disposal.

## Follow-up work

Deploy the reviewed fix, confirm worker initialization, then prepare a separate recovery plan before
touching DLQ messages.
