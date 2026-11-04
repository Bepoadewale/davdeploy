# test315 Test evidence: policy-critical unknown values

Date: 2026-11-04

Execution type: local unit tests only. No AWS requests, applies, destroys, or
resource creation were run.

Test ID: `pr315-generated-plan-critical-unknown-values`.

Repository: `Bepoadewale/davdeploy`, branch `feat/nova-plan-unknown-gates-v2`.

Customer repository: None. Test plans are synthetic fixtures.

Commit: pending PR commit.

AWS account: None. No AWS session was used.

AWS region: None. Tests use local synthetic plan documents.

## Scope

This evidence covers the bounded `after_unknown` checks added to the generated
Terraform plan policy. It is local evidence only; no AWS request or resource
mutation was performed.

## Local verification

- Focused command: `python -m pytest -q tests/test_generated_plan_policy.py`
- Result: 47 passed.
- Ruff: passed for `generated_plan_policy.py` and `test_generated_plan_policy.py`.
- Full `make verify`: 599 passed, Ruff, Actions configuration, OpenAPI snapshot,
  and Compose configuration passed.
- Documentation conventions and `git diff --check`: passed.
- Independent read-only review: no remaining blocker.
- Hosted CI: pending.

## Resources created

None. Tests use in-memory fixture documents only.

## Commands executed

`python -m pytest -q tests/test_generated_plan_policy.py` (47 passed),
`make verify` (599 passed with repository checks), and
`python3 scripts/check_doc_conventions.py`.

## Observed result

Known critical unknown values and missing/malformed metadata for monitored
resource types are denied, while an unknown computed identifier remains
eligible for human review.

## Teardown

No resources were created; no teardown was required.

## Final boundary

This is local policy-unit-test evidence only. It does not demonstrate a live
AWS plan, hosted Nova execution, apply, health verification, or cleanup.

## Limits

Only fields listed in `POLICY_CRITICAL_UNKNOWN_PATHS` are checked by this
change. It does not provide a generic unknown-value policy for every AWS
resource, resolve all typed references, establish ownership tags for every
resource, or estimate costs.
