# test438 — append-only customer CloudFormation template publishing

- Date: 2026-11-19
- Execution type: Source-level regression tests, local Terraform validation, and lock-free read-only protected-state plan; no apply
- Repository: `Bepoadewale/davdeploy`
- Commit: `5ec154f6f97b4062ca628969a5d1c27ca756838f` (plan source)
- Pull request: [#438](https://github.com/Bepoadewale/davdeploy/pull/438) (merged)
- Customer repository: N/A; this changes DavDeploy platform-owned template publishing.
- AWS account: `654654474502` (read-only protected-state plan)
- AWS region: `us-east-1`

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
- Initial lock-free protected-state plan attempt failed Terraform move validation with `Ambiguous move statements` at `main.tf` lines 116, 121, and 126. Terraform produced no plan; no lock was acquired, and no AWS resource or state was changed.
- After the move-graph correction on commit `5ec154f6f97b4062ca628969a5d1c27ca756838f`, a lock-free plan against the actual protected template-host state succeeded at `2026-11-19T10:31:19Z` with `TF_CLI_ARGS_plan=-lock=false`: exactly four object address moves (current `8c5d…` and retained `600…`, `7e…`, `f3…`), `0 to add, 0 to change, 0 to destroy`. This read-only plan has no Terraform monitor run ID.
- The successful read-only plan acquired no state lock and applied no resources. No apply was run.
- PR #438 merged as `cb78865b66815287478892fe012257cf964413db`; all seven required checks passed on final head `3ae046ebd661ca2a71eed49e6514337da1de62a3` in run [44593771329](https://github.com/Bepoadewale/davdeploy/actions/runs/44593771329).

## Resources created

None. The successful plan was read-only and used `-lock=false`; it changed no resource or state. No apply was run.

## Observed result

The first protected-state plan attempt exposed an ambiguous move graph and produced no plan. After correction, the plan against actual protected state showed exactly four address moves and `0 to add, 0 to change, 0 to destroy`. Historical addresses move to retained-map addresses, then the retained instances move to the shared content-hash-keyed resource. Regression coverage asserts unique move sources and the full migration chain. No apply was run.

## Teardown

None.

## Final boundary

The corrected lock-free plan passed with four address moves and zero adds, changes, or destroys. No lock or AWS resource/state change occurred. PR #438 is merged. A separate read-only plan for a changed template source remains future evidence; no apply is claimed. No customer CloudFormation template publication, stack, IAM role, or customer workload is claimed.
