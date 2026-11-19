# test441 — SQS queue encryption policy

- Date: 2026-11-19
- Execution type: Local generated-plan policy regression validation; no AWS
  execution
- Repository: `Bepoadewale/davdeploy`
- Customer repository: N/A; synthetic plan fixtures
- Commit: `e5408186daaa647c10dbce0b442164ed198f185b` (reviewed source base)
- Pull request: [#441](https://github.com/Bepoadewale/davdeploy/pull/441)
- AWS account: N/A; no AWS execution
- AWS region: N/A; no AWS execution

## Resources created

None. Tests use synthetic Terraform plan documents.

## Commands executed

- `PYTHONPATH=apps/api/src .venv-pr399/bin/python -m pytest
  tests/test_generated_plan_policy.py -q` — 271 passed, including enabled,
  disabled, and unknown SQS encryption cases
- Ruff on the changed policy and test files — passed
- `GITHUB_PR_NUMBER=441 python3 scripts/check_doc_conventions.py` — passed
- `git diff --check` — passed
- GitHub Actions run `44606644772` — all seven checks passed on source head
  `3700e88`
- GitHub Actions run `44607504888` — all seven checks passed on evidence head
  `52fcd83`
- Required checks for the current test-record head are tracked on PR #441

## Observed result

The policy requires known SQS-managed server-side encryption for every planned
`aws_sqs_queue`. The regression cases cover enabled, disabled, and unknown
values. Existing queue-policy checks remain unchanged. KMS-backed encryption,
queue retry/DLQ/visibility settings, and consumer behavior remain unsupported by
this policy rule. Local validation passed. Runs `44606644772` and `44607504888`
passed all seven checks on implementation head `3700e88` and evidence head
`52fcd83` respectively. Checks for the latest test-record head are tracked in
PR #441 before merge.

## Teardown

None. No AWS resources were created.

## Final boundary

No AWS resource or hosted control-plane state changed. This policy source is not
deployed and does not establish queue delivery, retry/DLQ operation, or a Nova
customer workload.
