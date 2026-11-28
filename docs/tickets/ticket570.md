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

- [x] Fixed feedback causes a reference to copy its declared output name and
      type exactly, without exposing raw generated values.
- [x] A valid typed reference repairs; mismatched types and undeclared output
      names still fail closed after bounded attempts.
- [x] Focused tests (215 passed), full verification (2,110 passed plus lint,
      Actions configuration, OpenAPI, and Compose syntax), documentation
      conventions, and diff checks pass locally.
- [ ] Required GitHub CI passes; satisfy any reviewer-required clean-room gate.
- [ ] One fresh post-deployment hosted plan-only result is recorded while the
      customer revision remains unapproved and no workload is applied/destroyed.

## Acceptance status

Prompt v31 now gives explicit SQS, Lambda, queue URL, and RDS secret output/type
pairs. The validator reports an undeclared output separately from a declared
output's type mismatch; both remain invalid. Regressions cover successful
bounded repair and fail-closed invalid responses without changing trusted
inputs. Focused/full local validation passes. CI, review, protected deployment,
and the post-deployment hosted v31 run remain pending.

## Tests / validation performed

- Hosted v30 run `56edfde0-63fe-4969-9314-ac3e5e510eab`: failed safely before
  Terraform planning. Two attempts, one repair; no plan artifact.
- Pre-request state: AWS account `654654474502`; no active local or hosted
  Terraform operations; source review remained unapproved.
- Implementation: fixed graph feedback and bounded semantic repair preserve
  output, resource, and type constraints; no reference is coerced or trusted
  without a matching declared output.
- Focused suites passed 215 tests. Full `make verify` passed 2,110 tests plus
  Ruff, Actions configuration, OpenAPI, and Compose syntax. Docs conventions
  and `git diff --check` passed.

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
