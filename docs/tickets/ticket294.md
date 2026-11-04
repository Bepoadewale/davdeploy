# ticket294 — Validate typed module input/output bindings

PR: https://github.com/Bepoadewale/davdeploy/pull/294
Branch: `feat/typed-module-bindings`

## Problem / goal

The composed graph can express dependency ordering but not which provider output is passed to which consumer input. That leaves the central data-flow contract implicit. Add typed port declarations for the first storage, data, queue, and API module families, validate bindings against checked-in contracts, and carry only typed references into lifecycle work. The customer still describes intent and does not choose AWS services.

## Current repo state

PR #293 merged distinct module type and instance identities. Dependencies are instance-scoped, but no input/output reference contract exists. The hosted CodeBuild worker remains single-module and the Lambda renderer remains disabled for ordinary customer execution.

## Research / references used

- `apps/api/src/davdeploy/domain.py` (`ArchitectureModule`, `ModuleContract`)
- `apps/api/src/davdeploy/module_contracts.py`
- `apps/api/src/davdeploy/universal_execution.py`
- `apps/api/src/davdeploy/cloud_execution.py`
- `apps/api/src/davdeploy/service.py` durable graph persistence

## Work planned for the PR

- Define typed, non-value-bearing input binding references and module port contracts.
- Declare stable input/output names and types for the initial API, storage, database, and queue architecture modules.
- Validate source instance/output, destination input, exact type compatibility, uniqueness, dependency ordering, and secret-reference handling.
- Serialize only references, never resolved secret or runtime values, through the execution boundary.
- Keep all hosted multi-module execution disabled and add focused tests for accepted and rejected graphs.

## Acceptance criteria

- [ ] Core module contracts expose typed input/output ports separately from module type identity.
- [ ] Multiple instances bind through explicit source instance IDs.
- [ ] Missing ports, type mismatch, ambiguous sources, undeclared edges, and inline secret values are rejected before dispatch.
- [ ] Valid bindings are included in the immutable compiled lifecycle graph and durable work payload.
- [ ] Legacy plans with no bindings remain valid.
- [ ] Hosted worker remains fail-closed for multi-module execution.
- [ ] Focused tests, full verification, clean-room cycle, and GitHub CI pass.

## Acceptance status

Pending implementation.

## Tests / validation performed

Pending implementation.

## Evidence files produced

No AWS workload evidence is expected. This PR adds typed graph validation only and does not enable or execute multi-module workloads.

## Boundaries

No AWS resources, customer data, credentials, migration, or hosted renderer gate changes are expected. No values from module outputs or secrets are resolved by the compiler.

## Follow-up work

Wire validated references to concrete renderer input/output schemas and the durable worker only after module-specific execution and hosted certification exist.
