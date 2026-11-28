# ticket566 — Bounded Nova plan access-profile feedback

PR: #566
Branch: `fix/nova-plan-permission-feedback-566`

## Problem / goal

Run the fixed customer plan permission-profile validator inside Nova's existing bounded proposal-repair loop, before staging input or starting CodeBuild. Return only stable, sanitized validation feedback so a repair can correct a compatible proposal or stop with an honest limitation. Do not widen IAM permissions or let Nova change trusted account, region, ownership, or policy inputs.

## Current repo state

- Backend `main` is `82fcd604ec3ed2e7272bc411bae903e8ca4bdfc9` (PR #565).
- Hosted v26 run `33afa2d7-9ce3-402e-86fc-e0cbd134c958` failed in CodeBuild with the fixed code `PLAN_PERMISSION_PROFILE_DENIED`; no plan artifact was produced and no customer resources were applied.
- The existing generation loop repairs schema/context errors, but the plan access profile is first checked in CodeBuild after Nova generation and input staging. The fixed error code does not explain which safe correction is possible.

## Research / references used

- `apps/api/src/davdeploy/terraform_generation.py`: bounded semantic repair and sanitized feedback allowlist.
- `apps/api/src/davdeploy/nova_plan_access.py`: fixed supported resource profile and exact scoped read policy.
- `apps/api/src/davdeploy/service.py`: `_prepare_generated_plan_run` currently generates, stages, and starts CodeBuild.
- `apps/api/src/davdeploy/nova_plan_codebuild.py`: trusted CodeBuild-side policy revalidation remains required.
- PR #565: safe runner failure codes; its log code identified this hosted failure without exposing proposal values.

## Work planned for the PR

- Add fixed classifications for model-correctable access-profile failures without including model-supplied resource names or raw exception details in feedback.
- Let the existing bounded generator validate the proposal against trusted account/region access-profile inputs and repair only with sanitized feedback.
- Keep CodeBuild validation as an independent defense-in-depth check before customer-role assumption.
- Add tests for correction, bounded exhaustion, trusted-input preservation, sanitization, and unchanged strict rejection by CodeBuild.
- Record the hosted v26 outcome and the PR checks in `docs/test/test566.md`.

## Acceptance criteria

- [x] Profile-incompatible proposals receive only fixed, allowlisted feedback in the existing bounded repair loop.
- [x] Trusted account, region, revision, and ownership context cannot change during repair.
- [x] Feedback never includes model-provided resource names, arbitrary exception text, credentials, or proposal values.
- [x] Uncorrectable/unsupported requirements fail with a bounded safe result before staging input or starting CodeBuild.
- [x] CodeBuild continues enforcing the exact fixed access profile before customer credentials are assumed.
- [x] Focused tests, full `make verify`, and docs conventions pass.
- [ ] Required GitHub CI passes.
- [ ] Post-deployment v27 outcome is recorded as plan-only evidence; no approval, apply, or customer-workload certification is claimed.

## Acceptance status

Implementation is complete. Focused and full local verification plus docs
conventions pass. Required CI, protected deployment, and post-deployment v27
hosted evidence remain.

## Tests / validation performed

Focused generation, access-profile, run, and customer-review suites: 181 passed.
`make verify`: 2,103 passed plus Ruff, Actions configuration, OpenAPI snapshot,
and Compose configuration checks. Docs conventions and `git diff --check` pass.
No local application containers were started. Required CI, PR review, protected
deployment, and one fresh hosted v27 plan-only run remain pending.

## Evidence files produced

- `docs/test/test566.md` — pre-PR v26 failure diagnosis and follow-up v27 verification record.

## Boundaries

No IAM action is added, no AWS workload is created, and no customer plan is approved, applied, or destroyed. Actual Terraform plan policy, application behavior, lifecycle, cost coverage, and full capability-matrix acceptance remain open.

## Follow-up work

After merge and protected deployment, run one fresh plan-only request against a
new unapproved revision with the same trusted architecture digest. Record its
safe outcome without applying the workload.
