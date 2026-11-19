# test438 — append-only customer CloudFormation template publishing

- Date: 2026-11-19
- Execution type: Source-level regression tests and local Terraform validation; no live AWS operations
- Repository: `Bepoadewale/davdeploy`
- Commit: pending fix for ambiguous migration graph
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
- Prior PR #438 CI run `44504878287` passed all seven checks before the migration-graph correction.
- A protected-state, lock-free read-only plan attempt failed during Terraform move validation with `Ambiguous move statements` at `main.tf` lines 116, 121, and 126. Terraform produced no plan; no lock was acquired, and no AWS resource or state was changed.
- The migration graph is corrected in source and regression coverage; a successful protected-state plan remains pending.

## Resources created

None. The read-only plan attempt stopped during move-graph validation before producing a plan. It acquired no lock and changed no live AWS resource or state.

## Observed result

The first protected-state plan attempt exposed an ambiguous move graph, so Terraform produced no plan. Historical addresses now move to the retained map, then retained instances move to the shared content-hash-keyed resource. Regression coverage asserts unique move sources and the full migration chain. A fresh protected-state plan must still prove the live state migration has zero existing-object mutations or deletions.

## Teardown

None.

## Final boundary

The first lock-free plan attempt failed before producing a plan; no lock or AWS change occurred. A fresh reviewed plan against protected template-host state is required before any explicit apply. No customer CloudFormation template publication, stack, IAM role, or customer workload is claimed.
