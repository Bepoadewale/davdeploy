# test338

Date: 2026-11-11
Execution type: Local automated and Terraform validation; no AWS mutation.
Customer repository: Not applicable; control-plane Terraform IAM conditions only.
Commit: implementation commit pending.
AWS account: `654654474502` (prior read-only identity verification; this PR makes no AWS calls).
AWS region: `us-east-1`

## Resources created

None.

## Commands executed

- `.venv/bin/python -m pytest tests/test_nova_plan_only_infra.py -q` — 10 passed.
- `.venv/bin/ruff check tests/test_nova_plan_only_infra.py` — passed.
- `terraform fmt -check -recursive infrastructure/terraform/serverless-control-plane` — passed.
- `terraform -chdir=infrastructure/terraform/serverless-control-plane validate` — passed.
- `make verify` — 867 passed; ruff, OpenAPI, Actions configuration, and Compose configuration checks passed. One existing Starlette/httpx deprecation warning remains.
- `python3.12 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Isolated `make local-proof` — pending.

## Observed result

The storage flag no longer grants API Lambda S3 state-object or KMS permissions by itself. Those permissions require both storage and state API flags; the HTTP state API route and its independent gates remain off in the reviewed storage-only configuration.

## Teardown

No resources created. Clean only this PR's isolated local validation stack and generated files after the clean-room run.

## Final boundary

The Terraform plan from run `42955035771` was reviewed but not applied because storage-only setup also granted the API Lambda S3/KMS state access. No AWS resources were changed by that plan. A fresh plan is required after this permission-gate fix is merged.
