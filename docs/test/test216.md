# test216

## Commands

```text
uv run ruff check apps/api/src/davdeploy/{models,domain,service,main}.py tests/test_public_blog.py
uv run pytest tests/test_public_blog.py -q
make openapi-update
make verify
```

## Result

Focused lint and tests passed. `make verify` passed configuration checks, Ruff,
313 tests, OpenAPI snapshot validation, and Docker Compose validation.

## Boundary

SQLite-backed deterministic tests only. No production post, comment, Cognito
identity, cloud resource, or customer data is created.
