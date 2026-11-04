# test303 — Executor dispatcher DynamoDB input

Date: 2026-11-04
Execution type: Local dispatcher unit tests, full suite and fixture-backed clean-room cycle; no AWS workload.
Customer repository: `Bepoadewale/davdeploy`
Commit: Pending implementation commit.
AWS account: Not applicable; this PR creates no AWS resources.
AWS region: Not applicable.

## Resources created

- No AWS resources.
- Local test and clean-room resources will be listed after validation.

## Commands executed

- `.venv/bin/pytest tests/test_renderer_dispatcher.py -q` — 11 passed.
- `.venv/bin/ruff check tests/test_renderer_dispatcher.py` — passed.
- `bash -n scripts/customer-workload-dispatcher.sh` — passed.
- `make verify` — 507 passed; OpenAPI and Compose configuration passed; one existing Starlette/httpx deprecation warning.
- `GITHUB_PR_NUMBER=303 .venv/bin/python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Clean-room cycle and PR CI — pending.

## Observed result

The dispatcher accepts the declared S3 bucket and DynamoDB table input/output port pairs for the Lambda/API renderer. Missing inputs, extra keys and incorrect source output names fail before the runner is invoked. Existing gates remain explicit; no customer execution route is enabled by this change.

## Teardown

No AWS workload was deployed. Temporary clean-room resources will be listed after validation.

## Final boundary

This proves local dispatcher contracts only. It does not certify Lambda data access, hosted worker recovery, or any customer deployment. Real composed AWS evidence remains required.
