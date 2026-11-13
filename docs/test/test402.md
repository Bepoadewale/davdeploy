# test402 — generated-plan EC2 metadata policy evidence

Date: 2026-11-13
Execution type: synthetic Terraform plan policy tests; local source verification
Customer repository: none; backend source worktree
Commit: `30b00b9` (expanded implementation; evidence refresh follows)
AWS account: none; no AWS credentials used
AWS region: none

## Resources created

No AWS resources or customer workloads were created. Tests use synthetic plan
JSON and local proposal objects.

## Commands executed

- `PYTHONPATH=apps/api/src /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest tests/test_generated_plan_policy.py tests/test_generated_deployment_contract.py -q`
- `make verify VENV=/Users/adewale/Projects/davdeploy/.venv-pr399`
- `GITHUB_PR_NUMBER=402 /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python scripts/check_doc_conventions.py`
- `git diff --check`
- GitHub Actions CI run `43502219872` passed all seven jobs for implementation
  commit `53ab621`.
- GitHub Actions CI run `43503068011` passed all seven jobs for evidence
  revision `d9fa007` (original coverage only).
- GitHub Actions CI run `43508435135` passed all seven jobs for expanded
  implementation commit `30b00b9`.

## Observed result

The focused plan-policy and structured-proposal suites passed: 222 tests.
Covered secure IMDSv2-enabled instance, launch-template, and launch-configuration
plans; explicitly disabled metadata endpoints; optional token rejection;
missing/malformed metadata settings; unknown token values; and regional
metadata defaults that do not require IMDSv2. `no_preference` is accepted as a
typed policy enum only for the regional-default setting and is denied by
actual-plan policy.

Full verification passed: 1,111 tests, Ruff, GitHub Actions configuration,
OpenAPI, and Docker Compose configuration checks. One existing Starlette/httpx
deprecation warning remains. Documentation convention and diff checks passed.
All seven hosted jobs passed for the expanded implementation revision. No AWS
calls or feature-gate changes occurred.

## Teardown

No resources required teardown.

## Final boundary

This is local synthetic evidence only. It does not prove AWS provider runtime
behavior, guest use of IMDSv2, role permissions, or Nova-hosted deployment.
