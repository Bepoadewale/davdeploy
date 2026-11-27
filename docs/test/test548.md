# test548 — template-host exact saved-plan binding

- Date: 2026-11-27
- Execution type: local unit/contract tests, mocked shell execution, offline
  Terraform validation, and isolated local clean-room cycle
- Repository: `Bepoadewale/davdeploy`
- Customer repository: N/A; platform-owned helper change
- Branch: `fix/template-host-saved-plan-20261127`
- Commit: `874d85b0ddfddb918bab4c0d517ac953f96a2c7d`
- Pull request: [#548](https://github.com/Bepoadewale/davdeploy/pull/548)
- AWS account: None; no AWS commands or credentials were used
- AWS region: None

## Commands executed

- `bash -n scripts/customer-aws-template-host.sh` — passed.
- `ruff check scripts/template_host_saved_plan.py tests/test_template_host_saved_plan.py tests/test_customer_aws_connection_contract.py` — passed.
- Focused pytest for `tests/test_customer_aws_connection_contract.py` and
  `tests/test_template_host_saved_plan.py` — 17 passed using the existing local
  Python test environment.
- `terraform -chdir=infrastructure/terraform/connection-template-host fmt -check -recursive` — passed.
- In a temporary copy of the root and its two YAML templates,
  `terraform init -backend=false -input=false` and `terraform validate` — passed
  with AWS provider 5.100.0. No remote backend was initialized and no plan was
  generated.
- `git diff --check` — passed.
- Full clean-room sequence in isolated worktree
  `/private/tmp/davdeploy-template-host-saved-plan-cleanroom-20261127` with
  Compose project `davdeploy-template-host-saved-plan-cleanroom-20261127`:
  clean, bootstrap, smoke, API contract, customer-plan E2E, fixture seed,
  simple/complex/Day-2/degraded demos, policy-failure and readiness-failure
  demos, trace check, and `make verify` — passed. `make verify` passed all
  2,035 tests. Final `make clean-local` stopped the project containers and
  removed that worktree's generated `.venv` and `.local`; a follow-up Compose
  inventory was empty.
- Mocked script execution proved plan creation does not apply; the valid digest
  causes Terraform to receive exactly the saved-plan path; a tampered plan and
  the old unbound `apply` operation fail before apply. The fake AWS command
  returns only the expected fixture account ID.

## Observed result

All local checks passed. The new runner applied only the supplied mocked saved
plan when the reviewed digest and manifest matched. Tampering and unbound apply
requests failed closed before the mocked Terraform apply command.

## Resources created

No AWS resources, Terraform state, S3 objects, or cloud artifacts were created.
The clean-room run created only local Compose containers, a local database
volume, and a virtual environment in its isolated worktree; those test-created
resources were removed during the final clean step.

## Teardown

The uniquely named clean-room Compose project was stopped, its test database
volume was removed, and its generated `.venv` and `.local` directories were
cleaned. No AWS cleanup was required.

## Limitations

- No current protected-state Terraform plan or apply was run.
- No result here establishes the exact AWS action set after PR #399's later
  template addition. That requires a separately reviewed fresh plan.
- Local plan artifacts require encrypted local disk storage; POSIX permissions
  do not encrypt their contents.

## Final boundary

No AWS, CloudFormation, S3, remote Terraform state, or control-plane change was
made. This is local source and mock evidence only; protected-state plan/apply
verification remains future work.
