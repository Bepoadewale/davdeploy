# test407 — trusted regional pricing evidence

Date: 2026-11-14
Execution type: Local implementation, unit/integration tests, and static Terraform formatting. No AWS execution.
Customer repository: `Bepoadewale/davdeploy`
Commit: `3ed2395089008ba0d790190edfa4fcca3faadd3b`
AWS account: Not used
AWS region: Not used

## Resources created

No AWS resources or customer workload resources were created.

## Commands executed

This is local implementation and static infrastructure validation. No live AWS
pricing request, customer plan, workload apply, or AWS resource mutation was
performed. The pricing tests use injected AWS Price List Query API responses.

Repository: `Bepoadewale/davdeploy`  
Branch: `feat/nova-regional-pricing-evidence`  
Base source: backend `main` PR #406, commit
`a6fff370479657a85949d59a82acee048cb46121`  
Deployed source remains PR #405, commit
`74016e70aa7a702ebf3338cf1fbb43d4f563a838`.


- `uv run --locked --extra dev pytest -q tests/test_generated_plan_pricing.py tests/test_generated_terraform_plan.py tests/test_generated_plan_artifacts.py tests/test_generated_plan_review.py tests/test_nova_plan_codebuild.py tests/test_nova_plan_runs.py tests/test_nova_plan_dispatch.py tests/test_nova_plan_only_infra.py` — 232 passed.
- `uv run --locked --extra dev ruff check apps/api/src/davdeploy/generated_plan_artifacts.py apps/api/src/davdeploy/generated_terraform_plan.py apps/api/src/davdeploy/generated_plan_pricing.py apps/api/src/davdeploy/nova_plan_codebuild.py apps/api/src/davdeploy/nova_plan_dispatch.py apps/api/src/davdeploy/service.py tests/test_generated_plan_pricing.py tests/test_generated_plan_review.py tests/test_generated_terraform_plan.py tests/test_nova_plan_codebuild.py tests/test_nova_plan_dispatch.py tests/test_nova_plan_only_infra.py tests/test_nova_plan_runs.py` — passed.
- `terraform fmt -check -recursive infrastructure/terraform/serverless-control-plane` — passed.
- `git diff --check` — passed.
- `python3 scripts/check_doc_conventions.py` — passed after aligning the ticket/evidence headings with repository conventions.
- `make verify` — passed: action configuration check, Ruff, 1,181 tests, OpenAPI snapshot check, and `docker compose config --quiet` (one existing Starlette/httpx deprecation warning).
- Full local clean-room lifecycle — not run. The prescribed `clean-local` command deletes local volumes and `.local` data, which requires explicit approval under the current local deletion rule. CI remains the clean integration proof.
- GitHub required checks — implementation commit run 43587685017 is still running. Its documentation check failed before the local heading correction; push the correction after the run ends and rerun CI.

## Observed result


The isolated Nova plan CodeBuild role is granted `pricing:GetProducts`; the
planner queries the public AWS price catalog with fixed service filters. The
only material resource currently priced is explicitly sized EBS gp3 with
default IOPS and throughput. Unsupported material resource types, custom
storage settings, internet transfer, or unknown usage remain incomplete and
block approval. The result is a list-price estimate, not a complete bill or a
spending limit. No customer plan or workload is approved by this evidence.

## Teardown

No cloud resources were created, so no AWS teardown was needed. The isolated local worktree and its Python environment are retained.

## Final boundary

PR #407 is draft and not deployed. No live AWS pricing request, customer plan, or customer workload lifecycle has been performed. Pricing covers only explicitly sized EBS gp3 with default performance settings; this does not establish complete application cost coverage or allow customer approval/apply.
