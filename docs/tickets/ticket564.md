# ticket564 — Improve bounded repair for Lambda health assertions

PR: #564  
Branch: `fix/nova-lambda-health-feedback-564`

## Problem / goal

The first hosted Nova plan-only request using prompt v25 failed before
CodeBuild. Its safe validation feedback says Nova proposed
`container_readiness` for an `aws_lambda_function`. The validator correctly
rejects that incompatible assertion. Existing feedback already names valid
declared alternatives, but the hosted model did not produce a valid repair
within its single bounded repair attempt. Make the generation task show the
valid assertion mapping clearly while preserving the fail-closed contract.

## Current repo state

- Backend `main` is `c79a24b5f11f694a6616d5555dd7391dafaed55f`; runtime v25
  code remains deployed from `104d804fe21bad4187a4dc1fc6332cf0923fb633`.
- PR #563 introduced prompt `terraform-nova2-contract-v25`; its final-head,
  merged-main CI, protected plan and exact saved-plan apply passed.
- Hosted run `8316ace6-88cd-4213-ad23-b4a249eebdd2`, revision
  `726d9ee0-65d2-4b41-9cf3-ad08e36c8c42`, failed with
  `NOVA_GENERATION_FAILED` / `proposal_invalid` before CodeBuild. Sanitized
  feedback was `incompatible_health_target` for a
  `container_readiness` assertion targeting an `aws_lambda_function`.
- The revision has digest
  `fb7384977baea8ff63b83d19be71ff5e0fcd54d45b19466a4f79a9722779cd4e`, no
  decision, and is approval-only. No saved plan or workload artifact was
  created.
- The authenticated workspace administrator and same-account connection are
  verified. The plan-only role is profile-verified. The Terraform run monitor
  has no active operations.

## Research / references used

- `apps/api/src/davdeploy/terraform_generation.py` — bounded generation task,
  typed health assertions and allowlisted validation feedback.
- `tests/test_terraform_generation.py` — compatible and fail-closed Lambda
  health assertion repair cases.
- `docs/test/test563.md` — deployed prompt v25 context.
- `docs/test/test564.md` — hosted v25 failure and this PR's verification.

## Work planned for the PR

1. Add a concise positive Lambda health assertion example to Nova's task and
   distinguish HTTP application health from queued-work processing.
2. Keep each example bound to declared resource IDs and same-plan API Gateway
   integration or SQS event-source relationships.
3. Add regression coverage for the prompt mapping and bounded repair while
   preserving strict validation when no compatible declared path exists.
4. Keep the existing validator and policy fail-closed; do not normalize an
   incompatible assertion, invent resources, remove requirements, or weaken
   health evidence.
5. Deploy the merged prompt through the protected control-plane saved-plan
   workflow, then run one fresh review-only hosted plan request and record its
   safe outcome.

## Acceptance criteria

- [x] Nova's task gives an exact valid `http_response` shape for a declared
  API Gateway stage wired to a Lambda, and an `event_processing` mapping only
  for a declared SQS-to-Lambda binding.
- [x] `container_readiness` remains invalid for Lambda and incompatible
  proposals still receive bounded, safe feedback.
- [x] Tests prove valid repair preserves declared application requirements
  and fails closed when the graph has no compatible declared health target.
- [x] No raw model proposal, credentials, or plan/state values are added to
  logs or evidence.
- [ ] Focused tests, full required verification, documentation checks, and
  final-head CI pass.
- [ ] Protected deployment uses an exact saved plan for the reviewed merged
  SHA; deployed runtime identity and health are verified.
- [ ] One fresh hosted plan-only request is inspected through safe diagnostics
  or a value-free saved-plan summary. It remains unapproved and unapplied.

## Acceptance status

The prompt examples and v26 version bump are implemented. Focused and full
local verification pass. Final-head CI, protected deployment, and one fresh
hosted v26 plan-only run remain open. No validator change, AWS mutation,
approval, apply, destroy, or customer workload certification is part of this
PR.

## Tests / validation performed

See `docs/test/test564.md`. The v25 baseline failed before CodeBuild with no
artifact; it is not evidence that this PR's prompt repair works. Focused tests,
full `make verify`, documentation conventions, and whitespace checks pass.
Record final-head CI and one post-deployment v26 hosted run before marking the
remaining criteria complete.

## Evidence files produced

- `docs/test/test564.md` records the hosted v25 failure baseline, local
  verification, and pending post-deployment v26 outcome.

## Boundaries

- Do not approve, apply, or destroy the synthetic workload.
- Do not change the customer connection or role, hosted state/locks, or AWS
  workload resources.
- Do not retrieve or publish raw proposals, saved plans, Terraform state,
  credentials, or signed artifact references.
- Do not claim the hosted Nova customer application was deployed or certified.

## Follow-up work

Use the next hosted run's earliest sanitized validation result to choose the
next bounded package. Avoid speculative schema, policy, or renderer expansion
before a valid hosted saved plan exists.
