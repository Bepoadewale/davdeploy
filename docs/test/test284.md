# test284 — Controlled serverless certification lifecycle

Date: 2026-11-03

Execution type: Local unit/contract verification and Terraform validation; no AWS workload execution.

Customer repository: None.

Commit: `569cb3c` (controlled serverless certification lifecycle implementation).

AWS account: None.

AWS region: None.

## Resources created

None. The hosted certification feature defaults to disabled and the workspace
allowlist defaults to empty.

## Commands executed

- `make verify` — passed; 403 tests, Ruff, configuration boundary, OpenAPI
  snapshot and Docker Compose configuration checks passed.
- `python3 scripts/check_doc_conventions.py` — passed.
- `terraform -chdir=infrastructure/terraform/serverless-control-plane validate` —
  passed.
- Focused cloud execution tests — 43 passed.
- `python3 scripts/check_doc_conventions.py` — passed.

## Observed result

Fixture-backed tests cover pinned artifact creation, plan chaining, exact apply
and destroy confirmations, health observation binding, destroy-plan chaining,
cleanup verification, workspace allowlisting, and duplicate saved-plan
submission rejection. The CLI and MCP forward the typed certification phase
fields to the governed API. No CodeBuild job or AWS workload was started.

## Teardown

No AWS resources were created. Local tests use disposable in-memory fixtures.
The repository's `make clean-local` procedure was not run because it deletes
the existing `.venv`, `.local`, and Docker volumes. Required CI uses a fresh
runner for integration verification.

## Final boundary

This is code and fixture evidence only. The AWS-hosted certification flag is off
by default, no workspace is allowlisted by default, and general customer
serverless execution remains disabled. A real hosted AWS lifecycle is still
required.
