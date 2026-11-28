# test570 — Nova typed output reference feedback

Date: 2026-11-28

Execution type: Real hosted AWS plan-only generation failure; no customer
workload apply was attempted.

Repository: `Bepoadewale/davdeploy`

Customer repository: Synthetic Nova validation workspace repository; source
contents were not retrieved.

Deployed baseline: PR #569 merge
`8890fa56d92a2cf7aee9023528d91833aa6b0052`.

Commit: deployed baseline `8890fa56d92a2cf7aee9023528d91833aa6b0052`.

AWS account: `654654474502`

AWS region: `us-east-1`

## Hosted v30 baseline

- Source plan `539f558d-16cf-4359-921a-9205a7e81bfe` remains
  `APPROVAL_REQUIRED` with no decision.
- Fresh review revision `4eff99fe-8c5f-4000-881b-c8f0f0718a84` retained the
  established digest, is `SUBMITTED`, has `decision=null`, and remains
  `UNEXECUTED_APPROVAL_ONLY`.
- Hosted plan-only run `56edfde0-63fe-4969-9314-ac3e5e510eab` failed before
  Terraform planning after two Nova attempts and one bounded repair. Prompt
  version: `terraform-nova2-contract-v30`; model:
  `us.amazon.nova-2-lite-v1:0`; input tokens: 15,053; output tokens: 6,582;
  latency: 24,956 ms; estimated cost unavailable.
- Sanitized feedback was `reference_type_mismatch`. The safe feedback stated
  to match a reference to its declared output. Raw proposal values were not
  retrieved.
- No Terraform plan artifact or customer resources were produced. No review
  decision, apply, destroy, or certification occurred.

## PR #570 changes and validation

- Prompt v31 lists valid output/reference pairs for SQS ARNs, Lambda ARNs,
  queue URLs, and RDS managed-secret ARNs.
- Validation now distinguishes a missing declared output from a mismatched
  value type. Both cases remain fail-closed; no policy or typed-reference
  acceptance rule is relaxed.
- Synthetic regressions cover exact-type repair, repeated type-mismatch
  rejection, and missing-output rejection without exposing generated IDs.
- Focused tests passed 215 tests. Full `make verify` passed 2,110 tests plus
  Ruff, Actions configuration, OpenAPI, and Compose syntax; docs conventions
  and diff checks passed. CI, review, protected deployment, and one fresh hosted
  plan-only v31 run remain pending.

## Resources created

None. The hosted request failed during proposal validation before Terraform
initialization or planning. The review revision is unapproved.

## Commands executed

- Authenticated `create-customer-review` and `submit-customer-review` using the
  established source plan and digest; output was filtered to safe revision
  fields.
- One hosted generated-plan-run request; run detail polled at 60-second
  intervals with allowlisted fields only.
- Read-only AWS identity, Terraform monitor, and hosted Terraform workflow
  checks before submitting the request.

## Observed result

The hosted request returned HTTP 202, then failed as
`NOVA_GENERATION_FAILED` / `proposal_invalid` with safe
`reference_type_mismatch` feedback. No CodeBuild plan artifact was produced.

## Teardown

No AWS resources or local containers were created by this hosted run; no
teardown was needed. Control-plane infrastructure and audit evidence were
preserved.

## Final boundary

No customer workload was applied, operated, destroyed, or certified. PR #570
is a prompt/validator-feedback repair; a future valid plan remains review-only
evidence until all separate hosted workload lifecycle gates pass.
