# test425 — bounded Nova intent schema repair

Date: 2026-11-17
Execution type: source tests and Terraform validation
Customer repository: none
Commit: `dbb6b13bc2b708f7ad71c26fa8e2f0d3851b03f8` (source)
AWS account: none
AWS region: none

Status: source implementation is complete locally. Tests use a gateway fixture;
no real model, AWS, or hosted calls were made for this package.

## Resources created

No AWS, model, or clean-room resources were created. Terraform validation wrote
local plugin metadata under retained directories
`/private/tmp/davdeploy-nova-bounded-repair-425-tfdata-app-runner` and
`/private/tmp/davdeploy-nova-bounded-repair-425-tfdata-serverless`.

## Verification

- Focused `tests/test_nova_intent.py`: 22 passed, covering zero, one, and two
  schema repair attempts, invalid configuration, bounded diagnostics, and
  aggregate usage.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`:
  1,303 tests passed; Ruff, Actions configuration, OpenAPI, and Compose checks
  passed. One existing Starlette/httpx deprecation warning remains.
- `terraform fmt -check` passed for both modified runtime roots. Terraform
  initialization with `-backend=false -lockfile=readonly` and `validate`
  passed for `app-runner-runtime` and `serverless-control-plane`.
- Documentation convention checks and `git diff --check` passed.
- GitHub Actions run [`44182459869`](https://github.com/Bepoadewale/davdeploy/actions/runs/44182459869)
  passed all seven required checks on source commit `dbb6b13`.
- The documentation-only evidence commit's fresh-head CI result will be
  recorded in the PR description.

## Commands executed

- `pytest -q tests/test_nova_intent.py`
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`
- `terraform fmt` / `terraform fmt -check` on both changed runtime roots
- Terraform `init -backend=false -input=false -lockfile=readonly` and
  `validate` on both changed roots
- `GITHUB_PR_NUMBER=425 python scripts/check_doc_conventions.py`
- `git diff --check`
- `gh pr checks 425 --watch --interval 120`

## Observed result

Full local verification passed, including 1,303 tests and Terraform validation
for both modified runtime roots. Focused intent tests passed (22). The repair
count defaults to one and accepts zero through two. All seven required checks
passed on source head `dbb6b13` in run `44182459869`.

## Teardown

No cloud resources were created. Terraform validation data directories are
retained; no cleanup or deletion ran.

## Final boundary

Tests use gateway fixtures. They did not call Bedrock, AWS, hosted services,
Terraform plans/applies, or customer workloads. The change does not alter
hosted feature flags, roles, credentials, or deployment resources.
