# test542 — Nova identifier repair feedback

Date: 2026-11-27
Execution type: Hosted generation failure evidence (no Terraform plan or AWS workload)
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance project)
Commit: control-plane prompt-v6 release based on `33e54879ebdd95a26ef65ff4e80e9d8416339e4c`
AWS account: `654654474502` (connected test account; no AWS workload operation)
AWS region: `us-east-1`

## Resources created

None. The v6 retry failed during Nova generation before CodeBuild, saved-plan
creation, or AWS execution. No customer workload is claimed as deployed.

## Commands executed

- Authenticated hosted API retry for generated plan run
  `0b1e4807-7532-45df-ad99-8edde41a82f4` after the prompt-v6 control-plane
  deployment; the API reused the run ID and the request used a new idempotency
  key.
- Retrieved the generated-plan run's bounded safe diagnostics. No raw proposal,
  prompt contents, credentials, or secret values were recorded.

## Observed result

The run failed generation after two model attempts and one repair. Safe schema
diagnostics were: three resource ID pattern mismatches, one resource graph
validation error, two health target ID pattern mismatches, and three cost
assumption ID pattern mismatches. Aggregate usage was 11,617 input tokens,
4,934 output tokens, and 17,777 ms; estimated cost was unavailable. There was
no CodeBuild build or saved plan. This failure motivates the v7 short-ID
contract and fixed repair guidance in PR #542.

## Teardown

Not applicable: the failed generation created no AWS resources, Terraform
workspace, or saved plan. No cleanup action was performed.

## Final boundary

This is hosted plan-generation failure evidence only. It does not prove a valid
plan, customer approval, Terraform apply, application behavior, lifecycle, or
certification. The control plane and audit records remain intact.

## Prompt-v7 local validation

- `pytest tests/test_terraform_generation.py tests/test_nova_plan_runs.py
  tests/test_customer_plan_review.py -q` — 99 passed.
- Ruff, `scripts/check_doc_conventions.py`, and `git diff --check` — passed.
- PR #542 CI, protected deployment, and one hosted retry after deployment are
  pending. No test workload or infrastructure was created.
