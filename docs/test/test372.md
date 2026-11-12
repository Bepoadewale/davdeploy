# test372 — bounded RDS subnet-group plan access

Date: 2026-11-12  
Execution type: Local policy verification; no AWS execution  
Customer repository: `Bepoadewale/davdeploy`  
Commit: Pending implementation commit  
AWS account: Not accessed  
AWS region: Not accessed

## Resources created

- No AWS resources, customer role, plan, approval, or workload have been
  created or changed by PR #372.
- Clean-room worktree and local service-resource details will be recorded
  after verification. No cleanup will be performed on retained local files or
  volumes without authorization.

## Commands executed

- Focused profile and customer role template tests:
  `uv run pytest -q tests/test_nova_plan_access.py tests/test_customer_aws_connection_contract.py`
  — 37 passed.
- Full backend verification: `make verify` — 1,038 tests passed; Ruff,
  Actions configuration, OpenAPI snapshot and Compose checks passed. The
  existing Starlette/httpx deprecation warning remains.
- `uv run ruff check apps/api/src/davdeploy/nova_plan_access.py tests/test_nova_plan_access.py tests/test_customer_aws_connection_contract.py`
  — passed.
- `python scripts/check_doc_conventions.py` and `git diff --check` — passed
  before the pending final evidence update.

## Observed result

- The plan profile accepts an RDS subnet group only when its name is concrete,
  in the bounded ARN-safe character set, and not the reserved `default` name.
  AWS normalizes subnet-group names to lowercase, so the session ARN uses the
  lowercase canonical name with the trusted target account and region.
- Subnet-group resources/typed references receive only the exact RDS
  `subgrp` ARN in the dynamic session policy. Role-level and session-policy
  action lists include `DescribeDBSubnetGroups` and `ListTagsForResource`;
  writes, data reads and secret contents remain denied.
- This is local policy/template evidence only. It does not prove live customer
  role permissions or a hosted Terraform plan.

## Teardown

No AWS cleanup is needed. Record local Compose-container status and retained
test artifacts after clean-room verification.

## Final boundary

This evidence must distinguish local policy/fixture validation from actual
hosted Terraform planning. No RDS or other AWS resource is created by these
tests. Regional pricing, customer role effective permissions, exact-plan
approval/apply, health, recovery, teardown and composed workload certification
remain separate gates.
