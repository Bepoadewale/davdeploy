# ticket166 — Restore hosted worker Bedrock Nova compatibility

PR: [#166](https://github.com/Bepoadewale/davdeploy/pull/166)
Branch: `fix/worker-bedrock-nova-provider`

## Goal

Restore worker startup for the deployed legacy `bedrock-nova` model-provider value without broadening model access or replaying failed work.

## Current state

The hosted worker DLQ contains failed messages because `configured_model_gateway()` rejected `bedrock-nova` before job processing began. Terraform currently emits `bedrock`; the deployed value is a legacy configuration alias.

## Acceptance criteria

- [x] The narrow legacy alias resolves to the existing Bedrock Nova gateway.
- [x] Unknown providers remain fail-closed.
- [x] No SQS message is replayed, deleted, or otherwise mutated by this PR.
- [x] Focused regression tests pass.

## Validation

See `docs/test/test166.md`.

## Boundaries and follow-up

Deploy through the reviewed runtime workflow, verify the worker starts, then separately inspect and explicitly authorise any DLQ replay or disposal.
