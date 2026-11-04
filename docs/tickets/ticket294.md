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

- [x] Core module contracts expose typed input/output ports separately from module type identity.
- [x] Multiple instances bind through explicit source instance IDs.
- [x] Missing ports, type mismatch, ambiguous sources, undeclared edges, and inline secret values are rejected before dispatch.
- [x] Valid bindings are included in the immutable compiled lifecycle graph and durable work payload.
- [x] Legacy plans with no bindings remain valid.
- [x] Hosted worker remains fail-closed for multi-module execution.
- [x] Focused tests, full verification, clean-room cycle, and GitHub CI pass.

## Acceptance status

Implemented for the initial private storage, NoSQL data, queue, secret-reference,
and serverless API ports. The static port registry is separate from renderer enablement;
unknown module types expose no bindable ports and cannot become executable as a result of
having a contract.

## Tests / validation performed

- `.venv/bin/python -m pytest -q tests/test_universal_execution.py tests/test_cloud_execution.py tests/test_planner_decisions.py` — **124 passed**.
- `make verify` — configuration check passed; Ruff passed; **458 tests passed**; OpenAPI snapshot matched; Docker Compose configuration passed.
- `.venv/bin/python -m ruff check ...` on changed Python files — passed.
- `git diff --check` — passed.
- Full isolated clean-room cycle passed from an empty worktree and unique Compose project: clean, fresh bootstrap, smoke, simple/complex/degraded/Day-2 demos, policy and readiness failures, customer-plan end-to-end, fixture seed, trace check, full verification, and teardown. All resources created by this test were removed.
- GitHub Actions run [41753761053](https://github.com/Bepoadewale/davdeploy/actions/runs/41753761053) — all seven checks passed: cloud-contracts, docs-conventions, local-e2e, policy, python, secrets, and supply-chain. The ticket-only follow-up commit will receive a fresh CI run before merge.

## Evidence files produced

No AWS workload evidence is expected. This PR adds typed graph validation only and does not enable or execute multi-module workloads.

## Boundaries

No AWS resources, customer data, credentials, migration, or hosted renderer gate changes are expected. No values from module outputs or secrets are resolved by the compiler.

## Follow-up work

Wire validated references to concrete renderer input/output schemas and the durable worker only after module-specific execution and hosted certification exist.
