# ticket270 — Add a typed renderer dispatcher for CodeBuild

PR: pending

Branch: `feat/typed-renderer-dispatcher`

## Problem / goal

The CodeBuild runner currently validates typed lifecycle work in the API, but its buildspec always calls the App Runner script and ignores the renderer binding. Add a deterministic dispatcher that routes only registered module IDs to their checked-in runner scripts and rejects unsupported or mixed work before invoking infrastructure tooling.

## Current repo state

PR #268 certified the standalone Lambda plus HTTP API Terraform root. PR #269 hardened its script with saved-plan digest checks and cleanup verification. The renderer registry still contains only the App Runner pilot, and the CodeBuild buildspec is hard-coded to that runner.

## Research / references used

`apps/api/src/davdeploy/module_renderers.py`; `apps/api/src/davdeploy/cloud_execution.py`; `infrastructure/terraform/serverless-control-plane/main.tf` CodeBuild buildspec; the App Runner and serverless API runner operation contracts.

## Work planned for the PR

Add serverless API to the checked-in renderer manifest without making it generally executable, add a bounded CodeBuild dispatcher that maps typed lifecycle work to the exact registered script and operation, preserve the existing App Runner build path, and add tests proving unknown/malformed work is rejected before invoking Terraform or a runner.

## Acceptance criteria

- [ ] CodeBuild dispatch uses only renderer paths from the checked-in registry.
- [ ] App Runner dispatch remains compatible with its existing saved-plan operations.
- [ ] Serverless API dispatch maps apply/destroy to saved-plan operations only.
- [ ] Unknown modules, invalid operations, extra commands, and unsupported mixed graphs fail closed.
- [ ] The serverless API module remains unavailable for customer execution pending service integration and hosted AWS certification.
- [ ] Focused tests and required CI pass.

## Acceptance status

In progress.

## Tests / validation performed

Not yet run.

## Evidence files produced

No real AWS workload is created by this PR. If that changes, add `docs/test/test270.md` before the run.

## Boundaries

No AWS resources are created, destroyed, or enabled. No IAM policy is broadened. The dispatcher accepts no arbitrary commands, scripts, Terraform roots, or customer-provided configuration paths.

## Follow-up work

Route approved serverless API plan and execution lifecycle requests from the service to the CodeBuild dispatcher, supply per-module saved-plan and artifact digests, then certify the hosted CodeBuild path with a disposable AWS workload before enabling it for customers.
