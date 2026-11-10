# test334 — exact-revision Nova plan history

Date: 2026-11-10
Execution type: Local API/service tests and static contract verification; no customer workload
Customer repository: N/A; no customer repository or workload was used
Commit: `338a403` for clean-room runtime; current implementation adds the
customer revision project ID and passed full local verification
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Resources created

No AWS or customer resources were created. Tests use local SQLite databases
and temporary directories. The PR-specific clean-room Compose stack, images,
virtual environment, and local seed data were removed after verification.

## Commands executed

```text
uv run pytest tests/test_nova_plan_runs.py -q
uv run ruff check apps/api/src/davdeploy/main.py apps/api/src/davdeploy/service.py tests/test_nova_plan_runs.py
make openapi-update
make openapi-check
make verify
python scripts/check_doc_conventions.py
git diff --check
COMPOSE_PROJECT_NAME=davdeploy-pr334-cleanroom-20261110 make local-proof
COMPOSE_PROJECT_NAME=davdeploy-pr334-cleanroom-20261110 make clean-local
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
- Clean-room `make local-proof` passed: 866 tests, API contract, demos, trace
  checks, policy checks, Actions configuration, Ruff, OpenAPI, and Docker
  Compose configuration passed at source commit `338a403`.
- `make clean-local` removed the exact PR-specific containers, volume,
  network, `.venv`, and `.local` seed data. The three uniquely named images
  were removed and absence of all project-scoped resources was verified.
- A small follow-up field on the customer revision response is covered by
  `tests/test_customer_plan_review.py`; the current working tree then passed
  `make verify` with 866 tests and all configured static checks.

## Teardown

No cloud resources were created. All local clean-room resources were removed
and their absence verified.

## Final boundary

This validates exact-revision filtering for the read-only tenant-scoped plan
history API. It does not prove hosted state, pricing, approval, apply, health,
recovery, or teardown.
