# test530 — CLI review and approval of generated plans

Date: 2026-11-27
Execution type: Local CLI command-routing validation
Customer repository: None for CLI command tests; hosted Nova acceptance repository is `Bepoadewale/fitness-backend`
Commit: `1825a2c9` (CLI implementation exercised by the recorded local checks)
AWS account: `654654474502` (hosted test account; no AWS changes in this PR)
AWS region: `us-east-1`

## Resources created

No AWS resources were created by the CLI command implementation or its unit
tests. The hosted acceptance plan run did not produce an artifact, so no
generated-plan approval was attempted.

## Commands executed

- `uv run --project . pytest -q tests/test_cli_generated_plan_approval.py tests/test_cli_auth.py`
- `uv run --project . ruff check apps/api/src/davdeploy/cli.py tests/test_cli_generated_plan_approval.py`
- `uv run --project . python scripts/check_doc_conventions.py`

## Observed result

- Safe artifact inspection routes to the tenant-scoped generated-plan artifact
  endpoint.
- Approval sends the exact supplied manifest SHA-256 digest to the governed
  backend endpoint.
- These tests do not approve or apply a plan; backend policy and evidence checks
  remain authoritative.
- Hosted approval evidence is unmet because the current Nova generation run
  failed before a Terraform plan artifact was created.

## Teardown

No AWS changes were made by this PR. No deletion was required.

## Final boundary

This evidence establishes only local CLI routing behavior and authentication
through the governed API. It does not establish a valid hosted Terraform plan,
approval, apply, application health or cleanup.
