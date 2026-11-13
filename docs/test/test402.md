# test402 — generated-plan EC2 metadata policy evidence

Date: 2026-11-13
Execution type: synthetic Terraform plan policy tests; local source verification
Customer repository: none; backend source worktree
Commit: `53ab621` (implementation revision covered by local tests)
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

## Observed result

The focused plan-policy and structured-proposal suites passed: 216 tests.
Covered secure IMDSv2-enabled instance and launch-template plans, explicitly
disabled metadata endpoints, optional token rejection, missing/malformed
metadata settings, and unknown token values. No AWS calls or feature-gate
changes occurred.

Full verification passed: 1,105 tests, Ruff, GitHub Actions configuration,
OpenAPI, and Docker Compose configuration checks. One existing Starlette/httpx
deprecation warning remains. Documentation conventions and diff checks passed.
Hosted CI is pending for the draft PR.

## Teardown

No resources required teardown.

## Final boundary

This is local synthetic evidence only. It does not prove AWS provider runtime
behavior, guest use of IMDSv2, role permissions, or Nova-hosted deployment.
