# ticket295 — Validate persisted module outputs and resolve typed references

PR: https://github.com/Bepoadewale/davdeploy/pull/295
Branch: `feat/validate-module-output-contracts`

## Problem / goal

PR #294 defines typed references between module ports, but a lifecycle outcome can still persist arbitrary JSON as module output. Before an output can safely feed a dependent module, validate it against the checked-in source module contract and resolve only declared references after the source has a successful durable state.

## Current repo state

PR #293 separates module type from instance identity. PR #294 declares typed ports for private storage, NoSQL data, queues, secret references, and the Lambda/API module, validates bindings during graph compilation, and serializes reference-only bindings. No worker consumes resolved outputs yet; multi-module CodeBuild execution remains disabled.

## Research / references used

- `apps/api/src/davdeploy/module_ports.py`
- `apps/api/src/davdeploy/universal_execution.py`
- `apps/api/src/davdeploy/service.py` module outcome persistence
- `apps/api/src/davdeploy/models.py` durable module output and state fields

## Work planned for the PR

- Validate typed module outputs before durable persistence, including HTTPS URLs, AWS ARNs, queue URLs, resource names, and secret references.
- Reject unknown output names and plaintext for secret-reference-only ports.
- Resolve a consumer's declared references only from dependency instances in an allowed successful state.
- Keep values scoped to the source instance and avoid resolving or fetching secret contents.
- Update the execution-goal handoff with verified PR #293/#294 status and the next durable-worker gaps.

## Acceptance criteria

- [ ] Typed outputs are validated before persistence for modules with checked-in port contracts.
- [ ] Unknown output ports, malformed values, insecure URLs, and plaintext secrets are rejected.
- [ ] Consumer references resolve only from declared dependency instances in a successful state.
- [ ] Existing untyped App Runner outcomes remain backward compatible and are not mislabeled as typed.
- [ ] Resolution never fetches or accepts secret contents.
- [ ] The execution handoff reflects merged #293/#294 and current remaining work.
- [ ] Focused tests, full verification, clean-room cycle, and GitHub CI pass.

## Acceptance status

Pending implementation.

## Tests / validation performed

Pending implementation.

## Evidence files produced

No AWS workload evidence is expected. This PR validates local durable output contracts only and does not enable composed execution.

## Boundaries

No AWS resource mutation, database migration, authentication change, or renderer enablement is expected. Output resolution returns only explicitly approved runtime output references.

## Follow-up work

Persist one module build/result identity per instance, conditionally claim dependency-ready waves, resume after successful outcomes, and reconcile uncertain runner outcomes without replay.
