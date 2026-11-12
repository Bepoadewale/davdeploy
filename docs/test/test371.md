# test371 — bounded RDS metadata access for Nova plans

Date: 2026-11-12  
Execution type: Local policy and contract verification; no AWS execution  
Customer repository: `Bepoadewale/davdeploy`  
Commit: Pending implementation commit  
AWS account: Not accessed  
AWS region: Not accessed

## Resources created

- No AWS resources or customer workload resources were created or changed.
- No customer role was installed or assumed. No plan or approval was created.
- Local clean-room proof has not yet run.

## Commands executed

- Focused plan-access and customer-role contract tests: `uv run pytest -q tests/test_nova_plan_access.py tests/test_customer_aws_connection_contract.py` — 27 passed.
- Full backend verification on the implementation tree: `make verify` — 1,028 tests passed; Ruff, Actions configuration, OpenAPI snapshot and Compose configuration checks passed. The existing Starlette/httpx deprecation warning remains.
- `uv run ruff check apps/api/src/davdeploy/nova_plan_access.py tests/test_nova_plan_access.py tests/test_customer_aws_connection_contract.py` — passed.
- `python scripts/check_doc_conventions.py` and `git diff --check` — passed before the final evidence update; rerun before committing.

## Observed result

- The plan profile supports `aws_db_instance`, `aws_rds_cluster`, and
  `aws_rds_cluster_instance` only when a concrete identifier can be bound to
  the trusted target account and region. The session policy includes exact
  database or cluster ARNs and explicit `DescribeDBInstances`,
  `DescribeDBClusters`, and `ListTagsForResource` metadata actions.
- Missing, wildcard, malformed, or expression-based identifiers fail closed.
  Typed identifier references must resolve to a same-family resource with a
  declared `resource_name` output.
- The customer plan-role template and session-policy action profile match.
  RDS modifications/deletes, database log contents, data API queries and
  Secrets Manager contents are not granted.
- This verifies local policy construction and template consistency only. It
  does not prove that an installed customer role has effective permissions or
  that a hosted Terraform plan can successfully read RDS metadata.

## Teardown

- No AWS cleanup was needed; the run made no AWS calls and created no AWS
  resources.
- Clean-room proof and its isolated local service resources are pending.

## Final boundary

This change does not enable hosted planning or apply, install a customer role,
provide complete VPC/subnet-group planning permissions, add database
provisioning renderers, integrate pricing, or certify application behavior,
recovery, or teardown. Pricing PR #318 remains held. Record clean-room, final
CI and review evidence here before merge.
