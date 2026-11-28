# ticket570 — Make typed output reference repair actionable

PR: #570
Branch: `fix/nova-reference-type-feedback-570`

## Problem / goal

The deployed v30 hosted plan-only run failed during bounded Nova proposal
validation with sanitized `reference_type_mismatch` feedback. The fixed
feedback already says to copy a declared output type, but Nova did not produce
a valid proposal after one repair. Improve the fixed guidance and regression
coverage without weakening typed-reference validation or changing trusted
requirements.

## Current repo state

- Main is PR #569 merge `8890fa56d92a2cf7aee9023528d91833aa6b0052`.
- Prompt `terraform-nova2-contract-v30` is deployed.
- Hosted run `56edfde0-63fe-4969-9314-ac3e5e510eab` failed before Terraform
  planning after two attempts and one bounded repair; no plan artifact or
  customer workload resources were produced.
- Source architecture plan remains unapproved; review revision
  `4eff99fe-8c5f-4000-881b-c8f0f0718a84` is submitted with no decision.

## Research / references used

- `apps/api/src/davdeploy/terraform_generation.py` fixed reference mismatch
  feedback and bounded semantic repair loop.
- `apps/api/src/davdeploy/generated_deployment_contract.py` typed output and
  reference validation.
- `tests/test_generated_deployment_contract.py` and
  `tests/test_terraform_generation.py` reference-shape fixtures.
- `docs/test/test569.md` and sanitized hosted v30 diagnostics.

## Work planned for the PR

- Review the typed-reference schema and current model guidance to identify a
  safe, bounded correction path for declared output type mismatches.
- Add a concrete reference/output matching example or correction sequence that
  does not guess provider output paths or types.
- Add bounded repair and fail-closed regressions, preserving trusted context and
  all architecture requirements.
- Bump the Nova prompt version.

## Acceptance criteria

- [ ] Fixed feedback causes a reference to copy its declared output name and
      type exactly, without exposing raw generated values.
- [ ] A valid composed reference proposal repairs; mismatched/unknown references
      still fail closed after bounded attempts.
- [ ] Focused tests, full verification, docs checks, and required CI pass; satisfy
      any reviewer-required clean-room gate.
- [ ] One fresh post-deployment hosted plan-only result is recorded while the
      customer revision remains unapproved and no workload is applied/destroyed.

## Acceptance status

Implementation has not started. The hosted v30 failure is the baseline; no
Terraform plan or workload mutation occurred.

## Tests / validation performed

- Hosted v30 run `56edfde0-63fe-4969-9314-ac3e5e510eab`: failed safely before
  Terraform planning. Two attempts, one repair; no plan artifact.
- Pre-request state: AWS account `654654474502`; no active local or hosted
  Terraform operations; source review remained unapproved.

## Evidence files produced

- `docs/test/test570.md` — hosted v30 failure and follow-up evidence.

## Boundaries

No customer plan approval, apply, destroy, or certification is part of this
PR. Do not retrieve raw Nova proposals, plan values, Terraform state, tokens,
or signed URLs. Do not add AWS resources or relax typed-reference checks to
satisfy the generated proposal.

## Follow-up work

After review and merge, deploy the exact merge SHA through the protected
saved-plan workflow, verify migrations/package hashes/health/admin CLI, then
create a fresh submitted review-only revision with the same trusted digest and
request one v31 plan-only run. Inspect only allowlisted safe diagnostics or a
value-free artifact summary.
