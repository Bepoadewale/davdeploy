# ticket264 — Universal execution contract integration

PR: [#264](https://github.com/Bepoadewale/davdeploy/pull/264)

Branch: `feat/universal-execution-contract`

## Problem / goal

Replace the execution request's hard-coded App Runner profile assumption with
an immutable, typed universal execution contract that supports composed module
graphs while retaining the existing deterministic authorization boundary.

## Current repo state

The compiler emits lifecycle operations and resource tags, but hosted run
creation still rejects every selected profile other than `aws-app-runner`.

## Research / references used

Existing `universal_execution.py`, composed deployment tests, and the current
customer execution runner contract.

## Work planned for the PR

Add typed execution operation validation, dependency ordering, plan-level
command metadata, and service integration without accepting free-form cloud
commands or weakening existing authorization checks.

## Acceptance criteria

- [x] The compiled graph is dependency ordered and immutable.
- [x] Service execution records preserve typed graph work rather than only audit metadata.
- [x] Existing App Runner execution remains compatible.
- [ ] Focused tests and full CI pass.

## Acceptance status

In progress.

## Tests / validation performed

`uv run pytest tests/test_universal_execution.py tests/test_composed_deployment.py tests/test_cloud_execution.py -q` — 19 passed.

## Evidence files produced

No AWS workload is created by this contract-only PR.

## Boundaries

No model or browser receives shell, Terraform, cloud-admin, or secret access.

## Follow-up work

Each module needs its own deterministic renderer and controlled real AWS
certification before its cloud operation can be enabled.
