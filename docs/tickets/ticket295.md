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

- [x] Typed outputs are validated before persistence for modules with checked-in port contracts.
- [x] Unknown output ports, malformed values, insecure URLs, and plaintext secrets are rejected.
- [x] Consumer references resolve only from declared dependency instances in a successful state.
- [x] Existing untyped App Runner outcomes remain backward compatible and are not mislabeled as typed.
- [x] Resolution never fetches or accepts secret contents.
- [x] The execution handoff reflects merged #293/#294 and current remaining work.
- [x] Focused tests, full verification, clean-room cycle, and GitHub CI pass.

## Acceptance status

Implemented for the typed port families introduced in PR #294. The resolver operates on
persisted reference data and success states, validates source outputs again, and returns
only declared values. The durable worker does not yet call the resolver; this PR provides
the validated boundary needed before worker scheduling is wired.

## Tests / validation performed

- `.venv/bin/python -m pytest -q tests/test_module_ports.py tests/test_cloud_execution.py tests/test_universal_execution.py tests/test_planner_decisions.py` — **136 passed**.
- `make verify` — configuration check passed; Ruff passed; **470 tests passed**; OpenAPI snapshot matched; Docker Compose configuration passed.
- `.venv/bin/python -m ruff check ...` on changed Python files — passed.
- `git diff --check` — passed.
- Full isolated clean-room cycle passed from an empty worktree and unique Compose project: clean, fresh bootstrap, smoke, simple/complex/degraded/Day-2 demos, policy and readiness failures, customer-plan end-to-end, fixture seed, trace check, full verification, and teardown. All resources created by this test were removed.
- GitHub Actions run [41756441895](https://github.com/Bepoadewale/davdeploy/actions/runs/41756441895) — all seven checks passed: cloud-contracts, docs-conventions, local-e2e, policy, python, secrets, and supply-chain.
- GitHub Actions run [41756993823](https://github.com/Bepoadewale/davdeploy/actions/runs/41756993823) on the ticket update — all seven checks passed: cloud-contracts, docs-conventions, local-e2e, policy, python, secrets, and supply-chain. The final ticket-only commit will receive one fresh check run before merge.

## Evidence files produced

No AWS workload evidence is expected. This PR validates local durable output contracts only and does not enable composed execution.

## Boundaries

No AWS resource mutation, database migration, authentication change, or renderer enablement is expected. Output resolution returns only explicitly approved runtime output references.

## Follow-up work

Persist one module build/result identity per instance, conditionally claim dependency-ready waves, resume after successful outcomes, and reconcile uncertain runner outcomes without replay.
