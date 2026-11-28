# ticket573 — Normalize one unambiguous managed RDS secret reference

PR: #573
Branch: `fix/nova-canonical-rds-reference-573`

## Problem / goal

The deployed v32 hosted Nova plan-only attempt failed before Terraform planning
with sanitized `unknown_reference_output` feedback after one bounded repair.
For the synthetic first-application intent, the only supported
`secret_reference` output is the AWS-managed RDS master secret ARN. Extend the
existing normalizer to canonicalize that output path only when the proposal
contains one RDS database and one Lambda secret-ARN consumer that already
references that exact database with `value_type=secret_reference`. Preserve
strict validation for ambiguous or mismatched references.

## Current repo state

- Backend `main` is PR #572 merge `2b0d8e8a53f0adfe26d5180ab7e03404be0ec48a`.
- Prompt version `terraform-nova2-contract-v32` is deployed.
- Hosted run `c5d6c546-5ac5-43c3-a907-a2c389caad7f` failed as
  `NOVA_GENERATION_FAILED` / `proposal_invalid`, with two attempts and one
  repair. Sanitized feedback reports `unknown_reference_output`; no Terraform
  plan artifact or customer resources were created.
- The submitted customer revision remains unapproved. No review decision,
  apply, destroy, or certification occurred.

## Work planned

- Extend only the existing managed RDS secret reference normalizer for the
  bounded typed-reference shape described above.
- Keep identity, output type, secret location, and resource uniqueness checks
  strict; leave unsupported shapes unchanged for normal validation to reject.
- Add synthetic regressions for canonicalization and fail-closed boundaries.
- Record CI and post-deployment plan-only outcome without claiming workload
  execution.

## Acceptance criteria

- [ ] Only one exact supported typed RDS-to-Lambda secret reference is
      normalized to the canonical provider output path.
- [ ] Wrong target, wrong type, multiple databases/consumers, and unrelated
      secret paths remain unchanged and fail normal contract validation.
- [ ] Focused tests, full verification, documentation checks, and required CI
      pass; no manual local clean-room stack is run.
- [ ] One fresh post-deployment hosted plan-only result is recorded while the
      customer revision remains unapproved and no workload is applied/destroyed.

## Validation and evidence

Pending implementation, focused/full local verification, GitHub Actions, and
one post-deployment hosted v33-or-current-contract plan-only request.

## Boundaries

No raw model output, secret value, credential, Terraform state, saved-plan
value, customer approval, AWS workload apply, destroy, or certification will be
retrieved or performed for this change. The hosted control plane remains
protected and only receives its normal reviewed source release.

## Follow-up

If a valid review-only plan is produced, inspect only its sanitized/value-free
summary and continue with the first missing hosted application gate. A plan
alone does not prove approved apply, application behavior, recovery, or cleanup.
