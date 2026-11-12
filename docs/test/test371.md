# test371 — bounded RDS metadata access for Nova plans

Date: 2026-11-12  
Execution type: Local policy and contract verification; no AWS execution  
Customer repository: `Bepoadewale/davdeploy`  
Commit: `4cda75bb8ae2cb358c8a2cb6ca4e9d268d2b981e` (`feat: scope Nova plan access to RDS metadata`)
AWS account: Not accessed  
AWS region: Not accessed

## Resources created

- No AWS resources or customer workload resources were created or changed.
- No customer role was installed or assumed. No plan or approval was created.
- The isolated local Compose project `davdeploy-pr371-cleanroom-20261112`
  created application/test containers, a project-scoped network, and a local
  Postgres volume. Its containers are stopped. Its volume, images, clean-room
  worktree `/private/tmp/davdeploy-pr371-cleanroom-20261112`, and `.venv` are
  retained; none were deleted.
- Local fixture records and demo deployment records were created in the
  isolated Postgres database by the standard local proof scripts.

## Commands executed

- Focused plan-access and customer-role contract tests: `uv run pytest -q tests/test_nova_plan_access.py tests/test_customer_aws_connection_contract.py` — 27 passed.
- Full backend verification on the implementation tree: `make verify` — 1,028 tests passed; Ruff, Actions configuration, OpenAPI snapshot and Compose configuration checks passed. The existing Starlette/httpx deprecation warning remains.
- Fresh worktree clean-room cycle:
  `COMPOSE_PROJECT_NAME=davdeploy-pr371-cleanroom-20261112 make local-proof` —
  passed bootstrap, smoke, API/CORS contract, local customer-plan E2E, fixture
  seed, trace check, `make verify` (1,028 tests), OpenAPI and Compose checks.
- `uv run ruff check apps/api/src/davdeploy/nova_plan_access.py tests/test_nova_plan_access.py tests/test_customer_aws_connection_contract.py` — passed.
- `python scripts/check_doc_conventions.py` and `git diff --check` — passed before this evidence update; rerun before committing.
- All seven GitHub CI checks passed for evidence commit `974798e07d4ed2f76eacc451ff5e775e6c340205` in run `43152444149`. That was the final implementation/evidence head before this documentation reconciliation.

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
- Local source review found no blocker: the three RDS actions are explicit,
  RDS ARNs use trusted account/region inputs and concrete validated names, and
  unsupported writes/data reads remain denied.

## Teardown

- No AWS cleanup was needed; the run made no AWS calls and created no AWS
  resources.
- Stopped the isolated Compose project with
  `COMPOSE_PROJECT_NAME=davdeploy-pr371-cleanroom-20261112 docker compose stop`.
- Its local Postgres volume, images, worktree and `.venv` remain for
  reproducibility. No deletion was performed.

## Final boundary

This change does not enable hosted planning or apply, install a customer role,
provide complete VPC/subnet-group planning permissions, add database
provisioning renderers, integrate pricing, or certify application behavior,
recovery, or teardown. Pricing PR #318 remains held. Implementation commit
`4cda75b` passed all seven GitHub CI jobs in run `43151728230`; evidence head
`974798e` passed all seven in run `43152444149`. Re-run checks after this
documentation reconciliation before merging.
