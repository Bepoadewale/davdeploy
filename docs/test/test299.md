# test299 — Private S3 renderer contract

Date: 2026-11-04  
Execution type: Local tests and Terraform validation; no AWS workload.  
Customer repository: `Bepoadewale/davdeploy`  
Commit: pending final implementation commit  
AWS account: Not applicable; no AWS credentials or resources used.  
AWS region: Not applicable.

## Resources created

- A Terraform provider cache under the new module root's ignored `.terraform/` directory.
- No AWS resources.

## Commands executed

- `terraform fmt infrastructure/terraform/customer-workload-private-s3` — passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-private-s3 init -backend=false -input=false` — passed; selected AWS provider `5.100.0`, recorded in `.terraform.lock.hcl`.
- `terraform -chdir=infrastructure/terraform/customer-workload-private-s3 validate` — passed.
- `bash -n scripts/customer-workload-private-s3.sh scripts/customer-workload-dispatcher.sh scripts/build_customer_executor_package.sh` — passed.
- `uv run ruff check ...` on changed Python and tests — passed.
- `uv run pytest -q tests/test_module_ports.py tests/test_module_renderers.py tests/test_private_s3_renderer_contract.py tests/test_renderer_dispatcher.py tests/test_planner_decisions.py` — 61 passed.
- `make verify` — 491 passed, one existing Starlette deprecation warning; OpenAPI snapshot and Compose config passed.
- `GITHUB_PR_NUMBER=299 python3.12 scripts/check_doc_conventions.py` and `git diff --check` — pending after the final documentation update.

## Observed result

- Terraform formatting and validation passed. Focused tests passed (61 tests); full `make verify` passed (491 tests) with one existing Starlette deprecation warning.
- The Terraform configuration sets an account guard, project/connection/plan tags, S3 public access blocks, bucket-owner-enforced ownership, AES256 encryption, versioning and a policy denying insecure transport.
- `force_destroy = false`; the runner checks all current and previous object versions before planning or applying destroy, so a non-empty customer bucket is not automatically emptied.
- Terraform state, saved plans and result artifacts are constrained to connection/project and plan/run prefixes. Apply uses a saved plan and checks its SHA-256 digest.
- Output normalization accepts only declared, non-sensitive `bucket_name` and `bucket_arn` outputs.
- The renderer is disabled in the Python registry. The dispatcher has a separate off-by-default certification gate, which the production adapter does not set.

## Teardown

No AWS resources were created, so no AWS teardown was needed. The generated provider cache is ignored under the module root. The required fresh local clean-room cycle has not run. The repository's `make clean-local` removes a generated PostgreSQL Docker volume plus local `.venv` and `.local` paths. The current personal `AGENTS.md` deletion rule requires explicit approval before deleting those artifacts. The PR remains draft until the clean-room requirement is satisfied.

## Final boundary

No AWS resource was created, updated, observed, or destroyed. This evidence proves configuration and local contracts only. It does not certify a live bucket lifecycle, hosted worker dispatch, input binding, rollback, or composed customer deployment.
