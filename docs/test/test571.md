# test571 — Safe Nova credential category feedback

Date: 2026-11-28

Execution type: Hosted v31 plan-only generation failure baseline and local
synthetic regression validation; no workload apply was attempted.

Repository: `Bepoadewale/davdeploy`

Customer repository: Synthetic Nova validation workspace; source contents were
not retrieved.

Deployed baseline: PR #570 merge
`df861459eae1bf642227c3c897adb4b3bb078607`.

Commit: PR #571 implementation is in progress; no v32 release is deployed.

AWS account: `654654474502`

AWS region: `us-east-1`

## Hosted v31 baseline

- Hosted plan-only run `9eec3f56-5f07-4ba3-8159-9a9c899590bc` failed before
  Terraform planning after two Nova attempts and one bounded repair. It returned
  sanitized `credential_value` feedback. No plan artifact was produced.
- The submitted review-only revision remains unapproved. No customer workload
  was created, applied, destroyed, or certified.
- Raw proposal and credential values were not retrieved.

## PR #571 implementation and local validation

- Prompt v32 supplies an allowlisted credential category and category-specific
  fixed guidance. Categories include password, secret, token, credential,
  authorization, and generic sensitive fields.
- Feedback carries only the fixed category and a validated AWS resource type.
  It omits the generated field name and value; sanitization discards untrusted
  category/type metadata and arbitrary fields.
- Credential validation remains fail-closed. Synthetic tests cover successful
  managed-secret repair, repeated literal-secret rejection within the bounded
  repair loop, category classification, and absence of field names/values from
  diagnostics and model context.
- Focused suites passed 220 tests. Full `make verify` passed 2,115 tests plus
  Ruff, Actions configuration, OpenAPI, and Compose syntax. Documentation
  conventions and diff checks passed. CI, clean-room review requirements,
  deployment, and the post-deployment v32 hosted request remain pending.

## Resources created

None. The hosted v31 request stopped before Terraform initialization/planning.
Local synthetic tests create no AWS resources.

## Commands executed

- One hosted plan-only request was previously submitted for v31. Safe run fields
  were inspected; raw proposals, plan values, state, credentials, and signed
  URLs were not retrieved.
- Local focused test suites for generation, customer plan review, and Nova plan
  runs passed (220 tests).

## Observed result

The deployed v31 failure remains a safe `credential_value` rejection. The v32
change makes the category actionable without revealing the rejected field name
or value; its full local and hosted gates are pending.

## Teardown

No AWS resources or local containers were created by these tests. No teardown
was needed. Existing control-plane infrastructure and audit evidence were
preserved.

## Final boundary

No customer workload has been applied, operated, destroyed, or certified. A
future valid plan remains unapproved plan-only evidence and does not establish
application behavior or lifecycle support.
