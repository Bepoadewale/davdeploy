# test372 — bounded RDS subnet-group plan access

Date: 2026-11-12  
Execution type: Local policy verification; no AWS execution  
Customer repository: `Bepoadewale/davdeploy`  
Commit: `757799c5ed4db5a36516395b69506b84351f458c`
AWS account: Not accessed  
AWS region: Not accessed

## Resources created

- No AWS resources, customer role, plan, approval, or workload have been
  created or changed by PR #372.
- Clean-room worktree: `/private/tmp/davdeploy-pr372-cleanroom-20261112`,
  checked out at the commit above.
- Isolated Compose project: `davdeploy-pr372-cleanroom-20261112`.
- The clean-room `make local-proof` completed successfully (1,038 tests and
  the local bootstrap, smoke, API contract, fixture customer-plan E2E, fixture
  seed, trace, OpenAPI and Compose checks). This used local fixtures only.
- All containers in that Compose project are stopped. Its Postgres volume,
  network, images, worktree and virtual environment are retained. No retained
  data or files were deleted.

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
- `COMPOSE_PROJECT_NAME=davdeploy-pr372-cleanroom-20261112 make local-proof`
  from the clean-room worktree — passed; containers are stopped and artifacts
  listed above are retained.
- Required CI run `43154578894` passed all seven jobs on implementation
  commit `757799c`. Final evidence head `01cb9c6` also passed all seven jobs in
  run `43155307470`.
- `python scripts/check_doc_conventions.py` and `git diff --check` — passed
  after the evidence update.
- Final-diff review found no blocker in the explicit action allowlist, exact
  trusted account/region/subnet-group ARN construction, concrete-name checks,
  typed-reference restrictions, or tests proving write/data/secret access
  remains outside this policy.

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

No AWS cleanup is needed. Clean-room Compose containers are stopped; the
project volume, network, images, worktree and virtual environment are retained.

## Final boundary

This evidence must distinguish local policy/fixture validation from actual
hosted Terraform planning. No RDS or other AWS resource is created by these
tests. Regional pricing, customer role effective permissions, exact-plan
approval/apply, health, recovery, teardown and composed workload certification
remain separate gates.
