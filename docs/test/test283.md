# test283 — Hosted serverless API lifecycle

## Current evidence

This is an in-progress PR. The first implementation slice changes the hosted
certification gate so that the API process environment cannot enable the
serverless renderer by itself. The worker copies the persisted run mode into its
private adapter context. The adapter accepts `aws-serverless-api` only when the
profile and `AUTHENTICATED_SERVERLESS_CERTIFICATION` mode match, and only then
adds the fixed CodeBuild certification variable.

The product API does not create serverless certification runs yet. No AWS
resources were created by this validation, and general customer execution
remains disabled.

## Local verification

Command:

```text
.venv/bin/ruff format apps/api/src/davdeploy/cloud_execution.py apps/api/src/davdeploy/module_renderers.py apps/api/src/davdeploy/service.py tests/test_cloud_execution.py tests/test_module_renderers.py
.venv/bin/ruff check apps/api/src/davdeploy/cloud_execution.py apps/api/src/davdeploy/module_renderers.py apps/api/src/davdeploy/service.py tests/test_cloud_execution.py tests/test_module_renderers.py
.venv/bin/python -m pytest -q tests/test_module_renderers.py tests/test_cloud_execution.py tests/test_renderer_dispatcher.py tests/test_serverless_artifact_builder.py
```

Result: Ruff passed; 57 tests passed. One upstream Starlette/httpx deprecation
warning was emitted.

## Still required

- Add administrator-authorized creation and queueing for the single-module
  serverless lifecycle.
- Validate each phase against the exact previous artifact or saved plan.
- Run the hosted AWS lifecycle and record apply, health, destroy, and cleanup
  evidence before considering renderer availability.
