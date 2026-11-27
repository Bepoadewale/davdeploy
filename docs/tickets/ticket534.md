# ticket534 — Preserve bounded Nova proposal failure diagnostics

PR: #534
Branch: `feat/nova-generation-diagnostics-534`

## Problem / goal

Hosted generated-plan run
`0b1e4807-7532-45df-ad99-8edde41a82f4` failed with
`NOVA_GENERATION_FAILED` before CodeBuild started. The safe run response only
said that Nova could not produce a validated proposal, so the failed attempt
does not show which bounded validation feedback exhausted repair.

## Current repo state

- `NovaTerraformGenerator` already sends schema and trusted-context feedback
  to Nova between bounded semantic attempts.
- The final `NovaTerraformGenerationFailed` exception did not retain that
  sanitized feedback, and the hosted run record exposed no validation detail.
- Raw model response, input, and provider exception content must remain out of
  the durable run result.

## Research / references used

- `apps/api/src/davdeploy/terraform_generation.py` bounded repair loop and
  existing feedback sanitizer.
- `apps/api/src/davdeploy/service.py` generated-plan run failure persistence
  and tenant-scoped status response.
- `tests/test_terraform_generation.py` and `tests/test_nova_plan_runs.py`.
- Hosted run `0b1e4807-7532-45df-ad99-8edde41a82f4` safe failure status.

## Work planned for the PR

- Preserve only fixed failure categories and canonical validation code/field
  feedback in `NovaTerraformGenerationFailed`.
- Store bounded model/prompt, attempt, retry, token, latency, cost, and
  validation metadata on the exact failed run.
- Return those diagnostics from the existing organization-scoped status API.
- Never store or return model output, prompt text, provider exception details,
  or arbitrary field names.

## Acceptance criteria

- [x] Proposal validation and context errors retain bounded code/path feedback.
- [x] Hosted run status exposes only fixed, sanitized generation diagnostics.
- [x] Raw model or provider content is absent from status and stored metadata.
- [x] Focused generator and run tests, Ruff, and diff checks pass locally.
- [x] Required hosted CI passes (all seven checks in run `45930341738`).
- [ ] A new hosted failure after deployment exposes usable safe diagnostics.

## Acceptance status

- [x] Local implementation and focused tests pass.
- [x] Required hosted CI run `45930341738` passed all seven checks.
- [ ] Runtime deployment and a new authenticated hosted retry remain pending.

## Tests / validation performed

- `uv run --project . --extra dev pytest -q tests/test_terraform_generation.py tests/test_nova_plan_runs.py` — 65 passed.
- `uv run --project . --extra dev ruff check apps/api/src/davdeploy/terraform_generation.py apps/api/src/davdeploy/service.py tests/test_terraform_generation.py tests/test_nova_plan_runs.py` — passed.
- `git diff --check` — passed.
- Hosted CI run `45930341738` — all seven required checks passed.

## Evidence files produced

- `docs/test/test534.md`

## Boundaries

- Diagnostics use the already-sanitized schema codes and canonical field
  paths; no Terraform expressions or values are exposed.
- This adds no new execution permission, approval, AWS command, or apply path.
- The prior hosted failure cannot be retroactively diagnosed because it
  persisted only the generic error summary.

## Follow-up work

After merge and protected deployment, rerun the submitted synthetic revision
with a new idempotency key. Inspect safe failure diagnostics or verify a real
saved-plan artifact. Keep approval and apply closed until regional pricing,
policy, ownership, and exact-plan evidence pass.
