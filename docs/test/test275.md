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

## Fresh clean-room cycle

At commit `fdd9e6c`, an isolated worktree at
`/tmp/davdeploy-cleanroom-pr275-20261103` used Compose project
`davdeploy-pr275-20261103`. This fail-fast sequence passed:

```text
make clean-local
make bootstrap-local
make smoke
make api-contract
make customer-plan-e2e
make demo-simple
make demo-complex
make demo-degraded
make demo-day2
make demo
make demo-failure
make demo-readiness-failure
make trace-check
make verify
make opa-test
make terraform-validate
make kubernetes-render
make clean-local
```

All targets passed, including 380 tests, OPA 3/3, offline Terraform validation,
and Kubernetes rendering. Final cleanup removed only the uniquely named
clean-room Compose resources and that worktree's generated `.venv` and `.local`
data. No AWS customer resources were created. This is local workflow evidence,
not AWS certification of the Lambda renderer.

GitHub Actions PR checks remain pending.
