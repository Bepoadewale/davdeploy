# test438 — append-only customer CloudFormation template publishing

- Date: 2026-11-19
- Execution type: Source-level regression tests and local Terraform validation; no live AWS operations
- Repository: `Bepoadewale/davdeploy`
- Commit: source PR commit pending
- Pull request: [#438](https://github.com/Bepoadewale/davdeploy/pull/438) (draft)
- Customer repository: N/A; this changes DavDeploy platform-owned template publishing.
- AWS account: N/A; no AWS calls made
- AWS region: N/A

## Purpose

Check that content-hash S3 template objects use stable key-derived Terraform addresses and receive deletion protection at initial creation, while preserving the existing output URL contract and state addresses through explicit migrations.

## Commands executed

- `.venv-pr399/bin/python -m pytest tests/test_customer_aws_connection_contract.py -q` — 9 passed.
- `.venv-pr399/bin/python -m ruff check tests/test_customer_aws_connection_contract.py` — passed.
- `terraform -chdir=infrastructure/terraform/connection-template-host fmt -check -recursive` — passed.
- `terraform -chdir=infrastructure/terraform/connection-template-host init -backend=false -input=false` — passed with locked AWS provider 5.100.0.
- `terraform -chdir=infrastructure/terraform/connection-template-host validate` — passed.
- `GITHUB_PR_NUMBER=438 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.

## Resources created

None. No Terraform plan or apply was run, and no live AWS resource was read or changed.

## Observed result

The shared object resource uses the content-hash key for each Terraform instance, applies `prevent_destroy` to the new and retained instances, and preserves the current URL output. Static regression coverage includes the current and historical state moves. No protected-state plan was produced, so this evidence does not establish the exact live state migration or deployment safety.

## Teardown

None.

## Final boundary

A separate reviewed plan against protected template-host state is required before any explicit apply. No customer CloudFormation template publication, stack, IAM role, or customer workload is claimed.
