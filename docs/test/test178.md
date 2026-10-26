# test178 — Customer project names

## Commands

`make openapi-update`

`.venv/bin/python -m pytest -q tests/test_project_name_contract.py`

`make verify`

## Result

Passed. The focused contract test passed (2 tests). Full backend verification passed: configuration boundary, Ruff lint, 295 tests, OpenAPI snapshot check, and Docker Compose configuration validation.

## Boundary

Local API contract validation only. No customer workload, credentials, or cloud resource is created or changed.

## Limitations

The frontend and hosted API deployment are verified separately in their coordinated pull requests.
