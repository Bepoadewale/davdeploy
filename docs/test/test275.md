# PR #275 validation evidence

## Scope and boundary

This PR scopes the existing Lambda/API renderer's state, artifacts, saved plans,
results, names and ownership tags by the verified cloud connection and project.
This is local validation only. It does not create AWS resources and does not
enable Lambda customer execution.

## Focused validation

- `bash -n scripts/customer-workload-serverless-api.sh scripts/customer-workload-dispatcher.sh` — passed.
- `python3 -m py_compile scripts/customer-serverless-artifact-build.py` — passed.
- `.venv/bin/ruff check scripts/customer-serverless-artifact-build.py apps/api/src/davdeploy/service.py tests/test_serverless_artifact_builder.py tests/test_serverless_renderer_contract.py tests/test_serverless_runner_safety.py tests/test_cloud_execution.py` — passed.
- `.venv/bin/python -m pytest tests/test_serverless_artifact_builder.py tests/test_serverless_renderer_contract.py tests/test_serverless_runner_safety.py tests/test_cloud_execution.py -q` — 41 passed, one Starlette deprecation warning.
- `terraform -chdir=infrastructure/terraform/customer-workload-serverless-api init -backend=false -input=false` and `terraform ... validate` — passed without using the cloud backend.
- `make verify` — passed: configuration check, Ruff, 380 tests, OpenAPI snapshot, and Compose config; one Starlette deprecation warning.
- `git diff --check`, Bash syntax check, Python bytecode compilation, and Terraform format check — passed.

Fresh clean-room validation and GitHub Actions checks are pending and will be
recorded here before merge.
