# PR #337 validation evidence

This file records permission-policy and infrastructure configuration validation. No customer workload is created or applied by this PR. AWS operations, if performed after merge, are limited to the exact reviewed DavDeploy control-plane Terraform state setup and are recorded below.

## Local checks

- `.venv/bin/python -m pytest tests/test_terraform_operations_bootstrap.py -q` — 7 passed.
- `.venv/bin/ruff check tests/test_terraform_operations_bootstrap.py` — passed.
- `terraform fmt -check -recursive infrastructure/terraform/terraform-operations-bootstrap` — passed.
- `terraform -chdir=infrastructure/terraform/terraform-operations-bootstrap validate` — passed.
- `make verify` — 867 passed; ruff, OpenAPI check, Actions configuration check, and Compose configuration check passed. One existing Starlette/httpx deprecation warning remains.
- `git diff --check` — passed.

## Pull request CI

Pending final-head checks.

## Terraform operations-bootstrap plan and apply

Pending. Record exact commit, run-monitor ID/root/PID/log, redacted plan summary, apply outcome, and post-apply IAM policy and AWS resource observations. Never include raw state, credentials, or sensitive plan values.
