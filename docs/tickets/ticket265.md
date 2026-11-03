# ticket265 — Typed universal execution runner boundary

PR: [#265](https://github.com/Bepoadewale/davdeploy/pull/265)

Branch: `feat/universal-execution-renderer`

## Problem / goal

Carry the approved universal lifecycle work from the durable execution request
into the trusted execution adapter without allowing arbitrary commands.

## Current repo state

PR #264 records typed module work with a run, but the trusted adapter receives
only profile and environment data.

## Research / references used

The existing CodeBuild/App Runner adapter boundary and the universal lifecycle
contract merged in PR #264.

## Work planned for the PR

Validate and pass only immutable typed lifecycle work to the trusted runner;
reject malformed or unsupported work before an execution backend is called.

## Acceptance criteria

- [x] The worker passes immutable typed lifecycle work to the adapter.
- [x] The adapter rejects malformed work without a cloud call.
- [x] Existing execution tests remain compatible.
- [ ] Focused tests and full CI pass.

## Acceptance status

In progress.

## Tests / validation performed

`make lint && uv run pytest tests/test_cloud_execution.py tests/test_universal_execution.py -q` — 19 passed.

## Evidence files produced

No customer workload is created by this contract-only PR.

## Boundaries

No free-form command, credential, or cloud-admin capability is introduced.

## Follow-up work

Individual renderers remain responsible for mapping typed modules to checked-in
Terraform and for their own real AWS certification.
