# ticket569 — Improve Nova managed database secret repair feedback

PR: #569
Branch: `fix/nova-rds-secret-ref-569`

## Problem / goal

The deployed v29 hosted plan-only run failed during bounded Nova proposal
validation with sanitized `credential_value` feedback. The model did not use
the existing typed reference to an AWS-managed RDS master secret. Improve the
fixed repair guidance and regression coverage while keeping the validator,
policy, and customer requirements unchanged.

## Current repo state

- Main is PR #568 merge `53ec7c71c6738ff3e46ffbe1a1d5a81e7cf1a7d1`.
- Prompt `terraform-nova2-contract-v29` is deployed.
- Hosted run `4685348a-b260-4ce5-8fd6-3b38f09397a5` failed before Terraform
  planning after two attempts and one bounded repair; no plan artifact or
  customer workload resources were produced.
- Source architecture plan remains unapproved. Its review revision
  `ec61602a-c4f9-4e2b-9f8d-e2e22f6f1c43` is submitted with no decision.

## Research / references used

- `apps/api/src/davdeploy/terraform_generation.py` fixed credential feedback,
  managed-secret examples, and bounded repair loop.
- `apps/api/src/davdeploy/nova_contract_generation.py` typed secret-reference
  validation and allowed placement.
- Existing provider validation and contract tests for RDS-managed secret
  outputs and Lambda environment references.
- `docs/test/test568.md` and hosted v29 run diagnostics.

## Work planned for the PR

- Make the safe `credential_value` correction more direct and unambiguous for
  the exact offending field while preserving the managed-secret contract.
- Add regression coverage for the feedback and bounded repair behavior,
  including fail-closed behavior when the proposal still contains credentials.
- Bump the Nova prompt version.

## Acceptance criteria

- [ ] Feedback names the allowed AWS-managed secret output and exact typed
      Lambda reference location without exposing any generated secret value.
- [ ] Valid managed-secret proposals repair and pass without changing trusted
      inputs; invalid credential values still fail closed.
- [ ] Focused tests, full verification, docs checks, required CI, and any
      reviewer-required clean-room gate pass.
- [ ] One fresh post-deployment hosted plan-only result is recorded while the
      customer revision remains unapproved and no workload is applied/destroyed.

## Acceptance status

Implementation has not started. The hosted v29 failure is the baseline; no
Terraform plan or workload mutation occurred.

## Tests / validation performed

- Hosted v29 plan-only run `4685348a-b260-4ce5-8fd6-3b38f09397a5`: failed
  safely before Terraform planning. Two attempts, one repair; no plan artifact.
- Local preconditions before the request: AWS account `654654474502`; zero
  active local or GitHub Terraform operations.

## Evidence files produced

- `docs/test/test569.md` — implementation and hosted plan-only evidence.

## Boundaries

No customer plan approval, apply, destroy, or certification is part of this
PR. Do not retrieve raw Nova proposals, plan values, Terraform state, tokens,
or signed URLs. Do not add AWS resources or weaken validation/policy to satisfy
the generated proposal.

## Follow-up work

After merge, deploy the exact merged commit through the protected saved-plan
workflow, verify migration/package hashes/health/admin CLI, then create a fresh
submitted review-only revision using the same trusted digest and request one
hosted plan-only run. Inspect only safe diagnostics or the value-free artifact
summary.
