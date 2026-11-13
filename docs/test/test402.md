# test402 — generated-plan EC2 metadata policy evidence

Date: 2026-11-13
Execution type: synthetic Terraform plan policy tests; local source verification
Customer repository: none; backend source worktree
Commit: `be1e111` (final PR evidence revision; merged as `653619d`)
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
- GitHub Actions CI run `43513116781` passed all seven jobs for final evidence
  revision `861b27b`.
- GitHub Actions CI run `43514648425` passed all seven jobs for final PR head
  `be1e111`.
- Merged-main CI run `43515569852` passed all seven jobs for merge commit
  `653619d`.
- GitHub Actions CI run `43511986076` passed all seven jobs for combined
  revision `079aea6`.
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

## Combined mainline verification

PR #401 merged to main at `53503f5` and adds network ACL policy checks. This
PR branch integrates that policy alongside the EC2 metadata checks and uses
shared policy version `nova-generated-plan-2026-11-13.3`. The combined focused
plan-policy and proposal-contract suites passed (232 tests). `make verify`
passed with 1,121 tests. The matrix records both checks and their limits.
Documentation conventions and diff checks passed; all seven hosted jobs passed
for this combined revision in run `43511986076`.

The PR evidence revision passed all seven checks in run `43513116781`; the
merged main commit passed all seven checks in run `43515569852`. No AWS
deployment or customer workload was part of these runs.

## Teardown

No resources required teardown.

## Final boundary

This is local synthetic evidence only. It does not prove AWS provider runtime
behavior, guest use of IMDSv2, role permissions, or Nova-hosted deployment.
