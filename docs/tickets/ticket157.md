# ticket157 — Bind approved image builds to authenticated Terraform plans

PR: Pending
Branch: `fix/image-build-plan-review-handoff`

## Problem / goal

The authenticated Terraform plan runner did not receive the approved image digest, so it produced a
foundation-only no-op plan even after image build success.

## Current repo state

The apply-run handoff was fixed in PR #156, but the plan-review runner has a separate environment
construction path with the same missing image inputs.

## Research / references used

- Authenticated service-plan evidence with only no-op foundation resources.
- `ProductService.create_terraform_plan_review_for_revision`.
- The bounded Terraform runner variable contract.

## Work planned for the PR

- Bind the latest image build for the exact revision/digest to authenticated non-destroy plan runs.

## Acceptance criteria

- [ ] An approved image build enables the App Runner resource in a fresh authenticated plan.
- [ ] Destroy-plan requests never receive the image/service inputs.
- [ ] Tests and CI pass.

## Acceptance status

Implementation and focused validation complete; CI pending.

## Tests / validation performed

- Ruff on the changed service module.
- Focused cloud execution tests.
- Diff whitespace validation.

## Evidence files produced

- `docs/test/test157.md`

## Boundaries

The change affects only plan input binding. It does not apply or destroy infrastructure.

## Follow-up work

Deploy the correction, generate the service plan, then perform the separate reviewed apply.
