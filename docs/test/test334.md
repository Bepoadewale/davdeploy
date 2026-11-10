# test334 — exact-revision Nova plan history

Date: 2026-11-10
Execution type: Local API/service tests and static contract verification; no customer workload
Customer repository: N/A; no customer repository or workload was used
Commit: implementation commit pending
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Resources created

No AWS or customer resources were created. Tests use local SQLite databases
and temporary directories. An isolated clean-room cycle remains pending.

## Commands executed

```text
uv run pytest tests/test_nova_plan_runs.py -q
uv run ruff check apps/api/src/davdeploy/main.py apps/api/src/davdeploy/service.py tests/test_nova_plan_runs.py
make openapi-update
make openapi-check
make verify
python scripts/check_doc_conventions.py
git diff --check
```

## Observed result

- Focused plan-run suite: 41 passed, including exact-revision selection,
  cross-project denial, cursor scoping, and the HTTP query parameter.
- Full `make verify`: 866 tests passed; Ruff, Actions configuration, OpenAPI,
  and Docker Compose configuration passed.
- OpenAPI snapshot was updated for the optional `revision_id` filter and
  `make openapi-check` passed.
- Documentation convention validation and `git diff --check` passed.
- No AWS, Bedrock, CodeBuild, state API, or customer workload calls occurred.
- Clean-room validation is pending.

## Teardown

No cloud resources were created. Local temporary test data is managed by the
test framework. If the required PR-specific clean-room stack is started, it
will be removed with `make clean-local` and its absence will be verified.

## Final boundary

This validates exact-revision filtering for the read-only tenant-scoped plan
history API. It does not prove hosted state, pricing, approval, apply, health,
recovery, or teardown.
