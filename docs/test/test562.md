# test562 — Nova root resource shape feedback

Date: 2026-11-28

Execution type: Hosted plan-only diagnostic baseline plus local contract tests

Customer repository: Synthetic DavDeploy acceptance case

Commit: `17df898510290134e0ef1770f51506d81474bb64` (deployed v23 baseline)

AWS account: `654654474502`

AWS region: `us-east-1`

## Resources created

No customer workload AWS resources were created or changed. The deployed
control plane was released through the protected workflow documented in
`docs/test/test561.md`.

## Commands executed

- Authenticated CLI safe read of generated-plan run
  `40c14f88-5a49-4df7-9fd0-199e6454b98a`, displaying only state, prompt
  version, attempt count, artifact presence, and allowlisted diagnostic fields.
- Focused generation/review/run test suite listed below.

## Observed result

- Hosted v23 run `40c14f88-5a49-4df7-9fd0-199e6454b98a` ended
  `FAILED` before CodeBuild after two attempts and one repair. No artifact was
  produced. Safe feedback contains ten `missing` or `extra_forbidden` entries
  collapsed to `resources[*]`; it does not expose the invalid key or proposal.
- Revision `0005b2f5-71b7-4efd-8b7e-70f2664a4e16` remains submitted with no
  decision. No workload plan, approval, apply, or destroy is claimed.
- Local tests now verify distinct fixed guidance for missing and extra root
  resource-object fields, redaction of arbitrary field names and input values,
  and transmission of the safe repair guidance into a bounded second attempt.
  Contract validation itself is unchanged.

## Implementation verification

- Focused command:
  `PYTHONPATH=apps/api/src /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest tests/test_terraform_generation.py tests/test_customer_plan_review.py tests/test_nova_plan_runs.py -q`
  — 147 passed; one pre-existing Starlette/httpx deprecation warning.
- `make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399 verify` passed
  2,095 tests; Ruff, Actions configuration, OpenAPI snapshot, and Compose
  checks passed. Documentation convention and diff checks passed.
- Isolated clean-room cycle, PR CI, and a fresh hosted v24 plan-only result
  remain pending.

## Teardown

No customer workload resources were created, so there was nothing to tear
down. No Terraform mutation was started for this test.

## Final boundary

The safe validator response identifies only a root resource-shape problem;
the unknown underlying model fields are intentionally unavailable. New
guidance tells Nova the fixed typed contract and leaves strict rejection in
place. A passing local test is not hosted plan, pricing, policy, health, or
lifecycle evidence.

