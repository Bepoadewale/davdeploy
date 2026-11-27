# test561 — Nova RDS secret output repair

Date: 2026-11-27

Execution type: Hosted plan-only diagnostic baseline plus local contract tests

Customer repository: Synthetic DavDeploy acceptance case

Commit: `1c4d36fa65ea34cd96f56c6356549b57fafd1d59` (deployed diagnostic baseline)

AWS account: `654654474502` (control-plane release only)

AWS region: `us-east-1`

## Commands executed

- Authenticated, read-only CLI requests for `/api/v1/me`, the latest customer
  review revision, and generated-plan-run history.
- Exact protected release apply run and saved-plan run inspection.
- Deployed API health check and release-artifact SHA256 comparison against all
  six control-plane Lambda code hashes.
- Focused and full local test commands listed below.

## Observed result

- Protected control-plane apply run `46076195000` succeeded for commit
  `1c4d36fa65ea34cd96f56c6356549b57fafd1d59` from saved plan `46075269981`.
- Its workflow confirmed database migrations completed successfully. The
  deployed API `/healthz` returned HTTP 200. All six named control-plane
  Lambda functions reported code hashes matching the exact versioned release
  artifact.
- A fresh submitted review-only revision
  `e28d434e-de59-457c-8e3a-95d37b43154c` preserved the preceding plan digest
  and had no approval decision.
- Hosted v22 run `64d26083-1521-4388-b2a6-e71b0054c72b` failed before
  Terraform/CodeBuild planning after two attempts. Its safe diagnostic was
  `unsupported_secret_output` at `resources[*]`; it has no artifact.
- No customer workload approval, apply, destroy, or certification occurred.
  The raw proposal, Terraform plan, state, and secret values were not fetched.

## Implementation verification

- `normalize_managed_lambda_secret_reference` now canonicalizes one typed
  secret-reference output only when one RDS resource and one Lambda
  `_SECRET_ARN` consumer uniquely identify the managed secret. It does not
  rewrite secret outputs on non-RDS resources or resolve ambiguous outputs.
- Fixed bounded-repair feedback names the only accepted output and the
  required RDS managed-password setting. Schema and policy checks remain
  unchanged.
- Focused command:
  `PYTHONPATH=apps/api/src /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest tests/test_nova_managed_secret_normalization.py tests/test_terraform_generation.py tests/test_customer_plan_review.py tests/test_nova_plan_runs.py -q`
  — 153 passed; one pre-existing Starlette/httpx deprecation warning.
- `make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399 verify` — 2,092
  tests passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose
  configuration checks passed. One pre-existing Starlette/httpx deprecation
  warning remains.
- Isolated clean-room proof, PR CI, and a fresh hosted v23 plan-only result
  remain pending.

## Resources created

No customer workload AWS resources were created or changed. There is no
customer workload cleanup to perform. The control-plane release was the only
AWS mutation and used the protected saved-plan apply workflow above.

## Teardown

No customer workload AWS resources were created, so no workload teardown was
needed. The control-plane release remains deployed as the authorized protected
control-plane version.

## Final boundary

The failure identifies an unsupported secret output but does not disclose its
model-authored shape. The new normalization intentionally handles only the
single unambiguous RDS/Lambda case; any unsupported or ambiguous output should
continue to fail validation. A passing local test is not hosted generation,
plan-policy, pricing, health, or lifecycle evidence.

