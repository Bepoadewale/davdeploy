# ticket321: Require encrypted EBS volumes in Nova plan policy

PR: #321 (draft)  
Branch: `fix/ebs-volume-encryption-policy`

## Problem / goal

The generated-plan policy currently checks whether the Terraform `after_unknown`
metadata leaves `aws_ebs_volume.encrypted` unresolved, but it does not reject a
known `false` value. This PR makes EBS volume encryption a required security
setting: every planned `aws_ebs_volume` must have `encrypted: true` before it can
be eligible for human review.

## Current repo state

- PR #315 added fail-closed handling for unknown EBS encryption values.
- `POLICY_CRITICAL_UNKNOWN_PATHS` lists `aws_ebs_volume.encrypted`, but
  `_check_databases()` does not cover EBS volumes and no known-false check exists.
- Generated Terraform plans are policy-reviewed before the separate approval
  record. This change affects policy eligibility only; it does not apply plans.

## Research / references used

- Local implementation: `apps/api/src/davdeploy/generated_plan_policy.py`.
- Local policy fixtures and tests: `tests/test_generated_plan_policy.py`.
- AWS EBS documentation explains that encryption is enabled by default only
  when the account/Region setting is enabled, and otherwise is optional when
  creating a volume: [Amazon EBS encryption](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-encryption.html)
  and [Enable encryption by default](https://docs.aws.amazon.com/ebs/latest/userguide/encryption-by-default.html).

## Work planned for the PR

- Add a deterministic EBS policy check requiring the final planned value
  `encrypted` to be exactly `true`.
- Keep unknown-value handling in place and return safe, stable policy findings.
- Add tests covering `false`, missing, unknown, and `true` values.
- Bump the generated-plan policy version because its approval semantics change.

## Acceptance criteria

- [x] A planned EBS volume with `encrypted: false` is denied.
- [x] A planned EBS volume with a missing encryption value is denied.
- [x] An unknown EBS encryption value is denied by the existing unknown-value check.
- [x] A planned EBS volume with `encrypted: true` is not denied for encryption.
- [x] Findings do not expose raw plan values and policy version changes.
- [x] Focused policy tests, `make verify`, and documentation conventions pass.
- [x] No AWS calls or resource mutations are performed.
- [ ] Required GitHub CI passes on this PR head.

## Acceptance status

Implementation and local verification are complete. Required GitHub CI remains
pending.

## Tests / validation performed

Validation performed:

- `uv run pytest -q tests/test_generated_plan_policy.py` — **65 passed**.
- `make verify` — **662 passed**; Ruff, Actions configuration, OpenAPI snapshot,
  and Compose configuration checks passed.
- `python3.12 scripts/check_doc_conventions.py` and `git diff --check` passed.
- No AWS calls or resource mutations were performed.

## Evidence files produced

No customer workload run is in scope. No `docs/test/test321.md` is required.

## Boundaries

- This change only blocks unencrypted planned EBS volumes in generated-plan
  policy evaluation.
- It does not change account-level EBS encryption defaults, create a KMS key,
  alter customer roles, or apply Terraform.
- It does not claim that all AWS storage encryption settings are fully covered.

## Follow-up work

Check other storage-bearing resource types and block-device mappings for
encryption requirements. Keep each new rule tied to an explicit final planned
value or a verified inherited encryption setting.
