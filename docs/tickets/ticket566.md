# PR #566 — Bounded Nova plan access-profile feedback

## Goal

Run the fixed customer plan permission-profile validator inside Nova's existing bounded proposal-repair loop, before staging input or starting CodeBuild. Return only stable, sanitized validation feedback so a repair can correct a compatible proposal or stop with an honest limitation. Do not widen IAM permissions or let Nova change trusted account, region, ownership, or policy inputs.

## Current state

- Backend `main` is `82fcd604ec3ed2e7272bc411bae903e8ca4bdfc9` (PR #565).
- Hosted v26 run `33afa2d7-9ce3-402e-86fc-e0cbd134c958` failed in CodeBuild with the fixed code `PLAN_PERMISSION_PROFILE_DENIED`; no plan artifact was produced and no customer resources were applied.
- The existing generation loop repairs schema/context errors, but the plan access profile is first checked in CodeBuild after Nova generation and input staging. The fixed error code does not explain which safe correction is possible.

## Research and references

- `apps/api/src/davdeploy/terraform_generation.py`: bounded semantic repair and sanitized feedback allowlist.
- `apps/api/src/davdeploy/nova_plan_access.py`: fixed supported resource profile and exact scoped read policy.
- `apps/api/src/davdeploy/service.py`: `_prepare_generated_plan_run` currently generates, stages, and starts CodeBuild.
- `apps/api/src/davdeploy/nova_plan_codebuild.py`: trusted CodeBuild-side policy revalidation remains required.
- PR #565: safe runner failure codes; its log code identified this hosted failure without exposing proposal values.

## Work

- Add fixed classifications for model-correctable access-profile failures without including model-supplied resource names or raw exception details in feedback.
- Let the existing bounded generator validate the proposal against trusted account/region access-profile inputs and repair only with sanitized feedback.
- Keep CodeBuild validation as an independent defense-in-depth check before customer-role assumption.
- Add tests for correction, bounded exhaustion, trusted-input preservation, sanitization, and unchanged strict rejection by CodeBuild.
- Record the hosted v26 outcome and the PR checks in `docs/test/test566.md`.

## Acceptance criteria

- [ ] Profile-incompatible proposals receive only fixed, allowlisted feedback in the existing bounded repair loop.
- [ ] Trusted account, region, revision, and ownership context cannot change during repair.
- [ ] Feedback never includes model-provided resource names, arbitrary exception text, credentials, or proposal values.
- [ ] Uncorrectable/unsupported requirements fail with an actionable safe result before staging input or starting CodeBuild.
- [ ] CodeBuild continues enforcing the exact fixed access profile before customer credentials are assumed.
- [ ] Focused tests, full `make verify`, docs conventions, and required CI pass.
- [ ] Hosted result is recorded as plan-only evidence; no approval, apply, or customer-workload certification is claimed.

## Validation

Pending implementation.

## Evidence files

- `docs/test/test566.md` (to be added with hosted and validation evidence).

## Boundaries and follow-up

No IAM action is added, no AWS workload is created, and no customer plan is approved, applied, or destroyed. Actual Terraform plan policy, application behavior, lifecycle, cost coverage, and full capability-matrix acceptance remain open.
