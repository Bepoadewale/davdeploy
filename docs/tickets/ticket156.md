# ticket156 — Bind approved image builds to service Terraform runs

PR: Pending
Branch: `fix/image-build-service-plan-handoff`

## Problem / goal

The service Terraform plan remained a no-op after a successful customer image build because the
guarded apply environment omitted the image digest and service-enable flag.

## Current repo state

Customer foundation and image build succeeded. The service plan contained no App Runner resource.

## Research / references used

- Authenticated plan evidence for the approved image-build revision.
- `ProductService.create_cloud_execution_run_for_revision`.
- The bounded App Runner runner environment contract.

## Work planned for the PR

- Read the latest successful image build for the same approved revision and digest.
- Pass only its immutable image identifier and a service-enable flag to the bounded apply runner.

## Acceptance criteria

- [ ] Service applies without an approved image remain foundation-only.
- [ ] A successful image build enables the service plan for the same revision only.
- [ ] Tests and CI pass.

## Acceptance status

Implementation and focused validation complete; CI pending.

## Tests / validation performed

- Ruff on the changed service module.
- Focused cloud execution tests.
- Diff whitespace validation.

## Evidence files produced

- `docs/test/test156.md`

## Boundaries

The fix only supplies an existing immutable image digest to a previously approved, guarded apply.
It does not introduce a destroy path.

## Follow-up work

Deploy the correction, regenerate the service plan, apply it, and ingest observed service state.
