# test283 — Hosted serverless certification-mode boundary

Date: 2026-11-03

Execution type: Local unit and contract tests; GitHub Actions CI. No AWS execution.

Customer repository: None.

Commit: `fb941d2` (hosted certification mode-bound renderer dispatch and test evidence).

AWS account: None.

AWS region: None.

## Resources created

None.

## Commands executed

- `.venv/bin/ruff check` on changed Python source and tests — passed.
- `.venv/bin/python -m pytest -q tests/test_module_renderers.py tests/test_cloud_execution.py tests/test_renderer_dispatcher.py tests/test_serverless_artifact_builder.py` — passed, 57 tests.
- `python3 scripts/check_doc_conventions.py` — passed.
- PR #283 CI run `41722464073` — all seven jobs passed.

## Observed result

The worker forwards the durable run mode to the adapter. A process environment
flag alone cannot enable serverless renderer dispatch. A matching persisted
serverless certification mode and profile is required. No customer execution
path was added.

## Teardown

No AWS resources were created. Temporary test resources were managed by the
local test fixtures.

## Final boundary

General customer serverless execution remains disabled. The product API does not
yet create this certification run mode. Creating and validating that lifecycle
is the next implementation step.
