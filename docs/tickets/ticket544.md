# ticket544 — Specific safe Nova resource validation feedback

PR: #544 (draft)
Branch: `fix/nova-specific-feedback-544`

## Problem / goal

Make known Nova resource argument validation failures actionable for both the
bounded repair attempt and an administrator reviewing safe diagnostics. Preserve
strict validation and never reveal generated values or raw validator messages.

## Current repo state

- Main is `f508951645327e0d2b77d0904d17d44a783e1e57`; PR #543's v8 prompt and
  fixed generic resource guidance are deployed by protected apply run
  `45955715362`.
- The one authorized v8 retry of hosted run
  `137ab46f-f5ee-4fa8-80cf-363ffc5f2736` failed before CodeBuild with
  `proposal_invalid`, 2 attempts, 1 repair, and one safe `value_error` at
  `resources[*]`. No plan or workload exists. This run must not be retried again.
- Six control-plane Lambdas match the versioned package for the deployed main
  commit; migration verification and `/healthz` passed.

## Research / references used

- `GeneratedResource.validate_arguments_and_outputs` in
  `apps/api/src/davdeploy/generated_deployment_contract.py`.
- Feedback redaction and prompt repair flow in
  `apps/api/src/davdeploy/terraform_generation.py`.
- Hosted v8 safe failure evidence in `docs/test/test544.md`.

## Work planned for the PR

- Classify only exact known resource validator causes into fixed safe issue
  codes and cause-specific fixed guidance.
- Preserve an allowlist at both model-feedback and hosted diagnostic boundaries.
- Bump the prompt version to v9 and add focused tests for every classification.
- After merge and protected deployment, create a fresh plan-only generation
  run; never approve or apply the customer workload.

## Acceptance criteria

- [x] Known resource errors return specific allowlisted issue codes and fixed
  corrective guidance.
- [x] Raw error causes, field names, generated values, and secrets remain hidden.
- [ ] Required hosted CI checks pass.
- [ ] A new post-deployment hosted run provides an inspectable plan or a more
  specific bounded failure. No customer workload is applied.

## Acceptance status

Implementation is locally verified; hosted CI, protected deployment, and a
fresh v9 plan-only run are pending. The customer workload remains unapproved
and unapplied.

## Tests / validation performed

- Focused tests: 105 passed, 1 existing Starlette deprecation warning.
- Full `make verify PY=/Users/adewale/Projects/davdeploy/.venv/bin/python`:
  2029 passed, 1 existing Starlette deprecation warning; Actions boundary,
  Ruff, OpenAPI snapshot, and Docker Compose configuration checks passed.
- Documentation conventions and `git diff --check`: passed before final CI.
- Hosted CI: pending.

## Evidence files produced

- `docs/test/test544.md` — v8 failure and later v9 plan-only evidence.

## Boundaries

- Never weaken validation or relax provider/account/region/policy constraints.
- Do not retry the failed v8 run again.
- Do not approve or apply any customer workload.
- Never print or persist raw model proposals, plan values, or credentials.

## Follow-up work

- Continue to exact-plan policy and pricing checks if the new run reaches a
  saved plan; otherwise use only bounded diagnostics to select another fix.
- The Nova goal remains incomplete until all hosted apply, behavior, lifecycle,
  recovery, cleanup, and capability matrix gates are evidenced.
