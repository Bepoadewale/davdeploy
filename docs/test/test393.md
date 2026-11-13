# test393

Test evidence for PR #393.

Date: 2026-11-13
Execution type: Local unit tests and static validation only; no AWS or customer workload
Customer repository: None; this validates backend manifest serialization.
Commit: Pending implementation commit.
AWS account: None; no AWS calls were made.
AWS region: None; no AWS calls were made.

## Scope

This change binds Nova's proposed health assertions, recovery requirements,
cost assumptions, assumptions, and limitations into the saved-plan manifest.
The manifest marks them `PROPOSED_UNVALIDATED_NOT_EXECUTED`; it does not claim
that probes ran or that costs were priced. Plan approval and execution remain
disabled at this boundary.

## Resources created

None. This was a local validation of serialization and digest-binding code.

## Commands executed

- `.venv/bin/python -m pytest tests/test_generated_deployment_contract.py tests/test_generated_plan_artifacts.py tests/test_nova_plan_codebuild.py tests/test_nova_plan_runs.py -q` — 122 passed.
- `make verify` — passed, including 1,064 tests and static/configuration checks.
- `git diff --check` — passed.
- `.venv/bin/python scripts/check_doc_conventions.py` — passed.

## Observed result

All four focused suites passed (122 tests). `make verify` passed (1,064 tests)
along with Ruff, OpenAPI, Actions configuration, and Docker Compose checks. The
test client emitted one pre-existing Starlette/httpx deprecation warning.

## Teardown

No external resources were created, so no teardown was required.

## Final boundary

This evidence covers local manifest serialization and regression tests only.
It does not establish hosted Nova plan success, pricing, probe execution,
customer approval, apply, operation, recovery, or destroy.

## Local validation

- Focused tests: `tests/test_generated_deployment_contract.py`,
  `tests/test_generated_plan_artifacts.py`, `tests/test_nova_plan_codebuild.py`,
  and `tests/test_nova_plan_runs.py` — 122 passed.
- `make verify` — 1,064 tests passed. Ruff, OpenAPI snapshot, Actions
  configuration, and Docker Compose configuration checks passed.
- `git diff --check` — passed.
- One existing Starlette/httpx deprecation warning was emitted by the test
  client.

## External effects

No customer plan, model call, AWS API call, infrastructure apply, or destroy
was performed for this change.

## Remaining evidence

Hosted pull-request CI and independent review are pending. This PR does not
implement or certify health probes, recovery execution, or regional pricing.
