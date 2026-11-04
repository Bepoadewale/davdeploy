# test327

Date: 2026-11-05
Execution type: local HTTP/API test fixture only
Customer repository: Not applicable; no customer workload was deployed.
Commit: Regression test implementation commit is recorded in PR #327.
AWS account: Not applicable; no AWS calls were made.
AWS region: Not applicable; no AWS calls were made.

## Resources created

No cloud or persistent resources. The test uses a temporary local SQLite database,
removed by pytest's temporary-directory fixture.

## Commands executed

- `uv run pytest -q tests/test_public_blog_api_access.py tests/test_public_blog.py tests/test_public_blog_edge.py`
- `uv run ruff check tests/test_public_blog_api_access.py`

## Observed result

5 tests passed. Anonymous GET requests succeeded for published post list, detail, and
comments. Anonymous protected-route requests were rejected by required-header
validation (HTTP 422).

## Teardown

Pytest removed its temporary local SQLite directory. No AWS cleanup was needed.

## Final boundary

The test is local-only. It created no AWS resources and did not alter production route
behavior.
