# ticket568 — Give Nova an exact SQS-to-Lambda event binding example

PR: #568
Branch: `fix/nova-event-binding-568`

## Problem / goal

The deployed v28 plan-only run failed during bounded Nova proposal validation
with sanitized feedback `missing_event_binding`. The queue-processing health
assertion referenced a declared SQS queue and Lambda, but the proposal omitted
an `aws_lambda_event_source_mapping` connecting them. Improve the fixed prompt
and repair guidance with the exact typed resource shape that satisfies the
existing contract. Keep validation and policy strict.

## Current repo state

- Main is PR #567 merge `909aba72f49eb5840752380b1dab6414f37b53ef`.
- Prompt `terraform-nova2-contract-v28` is deployed.
- Hosted run `86ccf87c-de06-4287-a1b2-b78fb0a0a77d` failed before CodeBuild;
  it produced no Terraform plan artifact or customer workload resources.
- The source architecture plan remains unapproved; the run's review revision
  remains submitted with no decision.

## Research / references used

- `apps/api/src/davdeploy/terraform_generation.py` fixed graph-feedback map
  and Lambda health examples.
- `apps/api/src/davdeploy/generated_deployment_contract.py` event-processing
  assertion requires a declared `aws_lambda_event_source_mapping` that
  references both the declared SQS source and Lambda target.
- `tests/test_generated_deployment_contract.py` defines the schema-compatible
  typed references for `event_source_arn` and `function_name`.
- `docs/test/test567.md` and this ticket's hosted v28 baseline.

## Work planned for the PR

- Add exact, schema-compatible mapping guidance: `event_source_arn` references
  the SQS queue's ARN output and `function_name` references the Lambda ARN
  output; preserve an `event_processing` assertion targeting that Lambda and
  naming that queue as its source.
- Keep the model's repair bounded and use only the declared queue and Lambda.
  If either resource or the existing architecture relationship is absent,
  return the current safe limitation rather than inventing a component or
  weakening the assertion.
- Add regression coverage for successful repair, fixed safe feedback, trusted
  context preservation, and failure when the required resources are absent.
- Bump the Nova prompt version to v29.

## Acceptance criteria

- [ ] The fixed prompt/guidance shows a schema-compatible typed SQS-to-Lambda
      mapping with references in the correct provider argument fields.
- [ ] A proposal with the required declared resources can repair and validate
      without changing trusted context or the original queued-work requirement.
- [ ] Missing or incompatible resources fail safely after the bounded attempt
      limit; no validator, policy, or health requirement is weakened.
- [ ] Focused tests, full verification, docs conventions, required clean-room
      cycle, and all seven required CI checks pass.
- [ ] One fresh post-deployment v29 plan-only result is recorded while the
      customer revision remains unapproved and no workload is applied/destroyed.

## Acceptance status

Bootstrap evidence only; implementation and verification are pending.

## Tests / validation performed

- Hosted v28 baseline and sanitized feedback are recorded in
  `docs/test/test568.md`.
- Implementation tests, clean-room verification, and CI are pending.

## Evidence files produced

- `docs/test/test568.md` — hosted v28 failure baseline and later v29 result.

## Boundaries

No customer plan approval, apply, destroy, or certification is part of this
PR. Do not retrieve raw Nova proposals, plan values, Terraform state, tokens,
or signed URLs. Do not add AWS resources or weaken policy to satisfy the
assertion.

## Follow-up work

After review and merge, deploy the exact merged commit through the protected
saved-plan workflow, verify migration/package hashes/health/admin CLI, then
create a fresh submitted review-only revision with the same trusted digest and
request one v29 plan-only run. Inspect only safe diagnostics or the
value-free artifact summary.
