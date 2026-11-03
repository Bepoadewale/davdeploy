# ticket270 — Add a typed renderer dispatcher for CodeBuild

PR: https://github.com/Bepoadewale/davdeploy/pull/270

Branch: `feat/typed-renderer-dispatcher`

## Problem / goal

The CodeBuild runner currently validates typed lifecycle work in the API, but its buildspec always calls the App Runner script and ignores the renderer binding. Add a deterministic dispatcher that routes only registered module IDs to their checked-in runner scripts and rejects unsupported or mixed work before invoking infrastructure tooling.

## Current repo state

PR #268 certified the standalone Lambda plus HTTP API Terraform root. PR #269 hardened its script with saved-plan digest checks and cleanup verification. The registry contains the enabled App Runner pilot and a disabled serverless API binding; CodeBuild was still hard-coded to App Runner.

## Research / references used

`apps/api/src/davdeploy/module_renderers.py`; `apps/api/src/davdeploy/cloud_execution.py`; `infrastructure/terraform/serverless-control-plane/main.tf` CodeBuild buildspec; the App Runner and serverless API runner operation contracts.

## Work planned for the PR

Add serverless API to the renderer manifest as explicitly disabled, add a bounded CodeBuild dispatcher that maps typed App Runner lifecycle work to the exact registered script and operation, preserve the pinned image-build path, and reject unknown or malformed work before invoking Terraform or a runner. Connect the existing plan-only review request to typed plan work. Do not enable the serverless renderer.

## Acceptance criteria

- [x] CodeBuild dispatch uses only the allowlisted checked-in renderer path.
- [x] App Runner dispatch supports plan, reviewed apply/destroy, and pinned image build operations.
- [x] The serverless API appears in the manifest as disabled and remains unavailable for customer execution.
- [x] Unknown modules, invalid operations, extra commands, and unsupported mixed graphs fail closed.
- [x] Authenticated plan review passes one typed plan-work item to CodeBuild.
- [x] Focused tests and required CI pass.

## Acceptance status

Merged at `93c895e6e40e80f20b71a6f3a21e3186ca63d576` on 2026-11-03. Required
CI passed. This merge deploys the dispatcher infrastructure only when the
separate approved Terraform workflow is applied; it does not enable the
serverless customer renderer.

## Tests / validation performed

- `make lint` passed.
- `make test` passed: 357 tests.
- Focused dispatcher, registry, and cloud-execution tests passed: 25 tests.
- `terraform -chdir=infrastructure/terraform/serverless-control-plane fmt -check -recursive` passed.
- `terraform -chdir=infrastructure/terraform/serverless-control-plane validate` passed.
- `GITHUB_PR_NUMBER=270 python3 scripts/check_doc_conventions.py` passed.
- `git diff --check` passed.
- PR #270 merged: [GitHub PR](https://github.com/Bepoadewale/davdeploy/pull/270).
- Required checks passed in [workflow run 41670185868](https://github.com/Bepoadewale/davdeploy/actions/runs/41670185868).

## Evidence files produced

No real AWS workload is created by this PR. If that changes, add `docs/test/test270.md` before the run.

## Boundaries

No AWS resources are created, destroyed, or enabled. No IAM policy is broadened. CodeBuild supports only the enabled App Runner renderer, one module per run; multi-module runs fail closed until each module has independent state and composition evidence. The isolated serverless API renderer remains disabled for hosted customer execution. The dispatcher accepts no arbitrary commands, scripts, Terraform roots, or customer-provided configuration paths.

## Follow-up work

Implement per-module saved-plan and artifact contracts, then certify the hosted CodeBuild path with a disposable AWS workload before enabling any additional renderer for customers. Compose multiple module states only after dependency, rollback, and cleanup behavior are independently validated.
