# test374 — deny unbound Secrets Manager value reads

Date: 2026-11-12  
Execution type: Local policy verification; no AWS execution  
Customer repository: `Bepoadewale/davdeploy`  
Commit: Pending implementation commit  
AWS account: Not accessed  
AWS region: Not accessed

## Resources created

- No AWS resources, customer roles, plans, approvals, or workloads were
  created or changed.
- Clean-room resources and retained artifacts will be recorded after the
  isolated verification run.

## Commands executed

- `uv run pytest -q tests/test_generated_plan_policy.py` — 149 passed.
- `make verify` — 1,044 tests passed; Ruff, Actions configuration, OpenAPI
  snapshot and Compose checks passed. One existing Starlette/httpx deprecation
  warning remains.
- `uv run ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py`
  — passed.
- `python scripts/check_doc_conventions.py` and `git diff --check` — passed
  before the final evidence update.

## Observed result

- Actual-plan IAM policy now denies explicit `GetSecretValue` and
  `BatchGetSecretValue` grants, plus action patterns such as `Get*` and
  `secretsmanager:*` that match either retrieval action.
- The check is case-insensitive, reports a fixed safe finding, and does not
  include policy resources or secret values in the finding message.
- `DescribeSecret` metadata-only permission remains eligible for human review.
- This guard does not yet bind an application permission to a typed RDS secret
  reference; runtime secret value access remains unavailable.

## Teardown

No AWS cleanup is needed. Clean-room container and retained-artifact status
will be recorded after verification.

## Final boundary

This is local actual-plan policy verification, not a hosted plan, approval,
apply, secret retrieval, or customer workload. Hosted planning, exact costed
approval, apply, health, recovery and teardown remain separate acceptance gates.
