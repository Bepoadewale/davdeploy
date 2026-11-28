# ticket571 — Add safe credential field categories to Nova feedback

PR: #571
Branch: `fix/nova-credential-location-feedback-571`

## Problem / goal

Hosted v31 failed during bounded Nova proposal validation with
`credential_value` feedback. The validator rejects the payload safely, but the
feedback exposes only `resources[*]`, so Nova must infer which kind of field
failed. Return a fixed credential-field category and matching correction while
never returning generated field names or values. Keep every secret and
credential check strict.

## Current repo state

- Main is PR #570 merge `df861459eae1bf642227c3c897adb4b3bb078607`.
- Prompt `terraform-nova2-contract-v31` is deployed.
- Hosted run `9eec3f56-5f07-4ba3-8159-9a9c899590bc` failed before Terraform
  planning after two Nova attempts and one bounded repair; no plan artifact or
  customer workload resources were produced.
- Source architecture plan remains unapproved; revision
  `bbe0446a-34b7-44ce-931d-200de4831d96` is submitted with no decision.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py` credential field
  detection and strict argument validation.
- `apps/api/src/davdeploy/terraform_generation.py` fixed validation-feedback
  allowlists and bounded Nova repair loop.
- Existing credential sanitizer and Nova plan diagnostics tests.
- `docs/test/test570.md` and sanitized v31 run diagnostics.

## Work planned for the PR

- Classify rejected credential-like fields using a small fixed vocabulary (for
  example password, secret, token, authorization, or generic sensitive field).
- Pass only the fixed category and a provider resource type that matches the
  safe AWS type pattern into sanitized feedback.
- Provide category-specific correction guidance; never include model field
  names, resource IDs, or values.
- Add bounded repair and fail-closed regressions, and bump the prompt version.

## Acceptance criteria

- [x] Credential feedback identifies only allowlisted category/resource-type
      metadata; generated field names and values never appear in API diagnostics,
      model repair context, errors, or tests' observable result.
- [x] A valid managed-secret proposal repairs; repeated literal credential
      values still fail closed within the attempt bound.
- [ ] Focused tests, full verification, docs checks, and required CI pass; satisfy
      any reviewer-required clean-room gate.
- [ ] One fresh post-deployment hosted plan-only result is recorded while the
      customer revision remains unapproved and no workload is applied/destroyed.

## Acceptance status

Implementation adds allowlisted credential categories and category-specific
fixed guidance without exposing model-generated field names or values. The
hosted v31 failure remains the baseline; v32 has not yet been deployed or run.

## Tests / validation performed

- Hosted v31 run `9eec3f56-5f07-4ba3-8159-9a9c899590bc`: failed safely before
  Terraform planning. Two attempts, one repair; no plan artifact.
- Pre-request state: AWS account `654654474502`; no active local or hosted
  Terraform operations; source review remained unapproved.
- Focused credential/generation/review/run suites: 220 passed. Full verification,
  documentation checks, final CI, clean-room review gate, deployment, and
  hosted v32 result remain pending.
- Full `make verify`: 2,115 tests passed; Ruff, Actions configuration,
  OpenAPI, Compose syntax, documentation conventions, and diff checks passed.

## Evidence files produced

- `docs/test/test571.md` — hosted v31 failure and follow-up evidence.

## Boundaries

No customer plan approval, apply, destroy, or certification is part of this
PR. Never retrieve raw Nova proposals, plan values, Terraform state, tokens, or
signed URLs. Never echo credential-like field names or values. Do not add AWS
resources or relax contract validation to satisfy the generated proposal.

## Follow-up work

After review and merge, deploy the exact merge SHA through the protected
saved-plan workflow, verify migrations/package hashes/health/admin CLI, then
create a fresh submitted review-only revision with the established trusted
digest and request one v32 plan-only run. Inspect only allowlisted safe
diagnostics or a value-free artifact summary.
