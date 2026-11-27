# ticket551 — field-aware safe feedback for unknown Nova schema errors

PR: [#551](https://github.com/Bepoadewale/davdeploy/pull/551) (draft)
Branch: `fix/nova-safe-validation-feedback-551`

## Problem / goal

The hosted v14 generation attempt failed before CodeBuild. The safe diagnostics
reported an invalid resource ID with useful fixed guidance, but also collapsed
two unknown typed-validator error codes to `invalid` at the root `proposal`
field. Preserve a validated schema field path for unknown error types and give
Nova bounded field-specific correction guidance without exposing raw validator
messages, field values, or proposal data.

## Current repo state

- Backend main is `edf8d2425e0a76015067a5c28b306493f7c2abb7`, PR #550 merged.
- PR #550's v14 prompt is deployed by protected plan `45997786571` and saved-plan
  apply `45998758698`. Apply completed with 0 adds, 8 changes, 0 destroys;
  migrations passed; all six Lambdas are Active/Successful and match the release
  package; `/healthz` returned HTTP 200.
- Fresh review revision `a96bdf2d-6c44-4ba6-a813-53da9f2f4251` is `SUBMITTED`,
  has no decision, and uses content digest
  `fb7384977baea8ff63b83d19be71ff5e0fcd54d45b19466a4f79a9722779cd4e`.
- Hosted plan-only run `ec8a79ce-3c5c-4e2e-9b66-d16da1f0f6ab` failed before
  CodeBuild as `NOVA_GENERATION_FAILED` / `proposal_invalid`. Prompt v14 made 2
  attempts (1 repair); diagnostics reported one `string_pattern_mismatch` at
  `resources[*].resource_id` with fixed ID guidance and two `invalid` errors at
  `proposal`. No artifact, CodeBuild build, or workload was created.
- The synthetic source architecture includes nine modules marked
  `execution_supported=false` and uses fixture catalogue
  `aws-v1-fixture-2026-10-minimum-infrastructure` ($50–$170/month). This test is
  for bounded generation diagnostics only; it cannot satisfy the real-price or
  supported composed-plan acceptance gates.
- The customer review remains unapproved. No customer workload was approved or
  applied.

## Research / references used

- `apps/api/src/davdeploy/terraform_generation.py` — Pydantic feedback
  sanitization, canonical field paths, guidance allowlist, and prompt version.
- `apps/api/src/davdeploy/generated_deployment_contract.py` — strict typed
  proposal schema and graph validation.
- PR #550 and `docs/test/test550.md` — v14 source and hosted failure evidence.
- Pydantic errors are untrusted diagnostic input. Only stable codes, paths
  composed from schema-allowlisted segments, and fixed guidance may cross into
  a repair prompt or persisted run diagnostics.

## Work planned for the PR

1. [x] Preserve a canonical field path for unknown validator codes only when it
   is composed from allowed contract fields; otherwise use `proposal`.
2. [x] Select field-specific fixed correction guidance from an allowlist. Never
   use the validator's message, input value, arbitrary context, or model output.
3. [x] Keep contract validation strict and keep invalid proposals out of
   CodeBuild.
4. [x] Bump the prompt contract version and add regression tests for unknown
   error types, path truncation, and raw-data redaction.
5. After protected deployment, create a fresh submitted review revision and
   make one v15 plan-only run. Record only bounded diagnostics or sanitized
   artifact metadata; do not approve or apply a workload.

## Acceptance criteria

- [x] Unknown Pydantic error types retain only safe canonical field paths.
- [x] Field-specific guidance is fixed, allow-listed, and contains no validator
  text, field value, or proposal content.
- [x] Unknown paths fail closed to a safe parent field or `proposal`.
- [x] Existing graph and resource feedback behavior remains covered; malformed
  proposals still fail before CodeBuild.
- [x] Focused tests, full local verification, documentation checks, and all
  seven required PR CI checks pass for code head `cb74f8cd` in run
  `46013241761`. Any subsequent source or evidence commit must also pass all
  required CI checks before merge.
- [ ] One fresh v15 hosted run reaches an inspectable saved plan or returns
  actionable bounded feedback before CodeBuild. No approval or workload apply
  occurs.
- [x] No customer approval, customer Terraform plan/apply/destroy, or AWS
  workload mutation is part of the observed v14 failure.

## Acceptance status

Implementation commit `5a11f3ce8f5b3528b11211348617e761130bc217` now preserves
canonical field paths for unknown validator codes, truncates unsafe suffixes,
and supplies fixed field-category guidance. Focused tests (39), full local
verification (2,051 tests plus lint/config/OpenAPI/Compose checks), Ruff,
documentation conventions, and diff checks pass. All seven required PR CI
checks passed in run `46013241761` on code head `cb74f8cd`. Further commits
must pass CI on their exact final head before merge. Protected v15 deployment
and the fresh v15 hosted run remain pending.

## Tests / validation performed

- The pre-implementation v14 run and safe diagnostics are recorded in
  `docs/test/test551.md`.
- The v15 implementation and local checks are recorded in
  `docs/test/test551.md`.
- Hosted v15 evidence remains pending deployment of this PR.

## Evidence files produced

- `docs/tickets/ticket551.md`
- `docs/test/test551.md`

## Boundaries

- Do not weaken the typed proposal contract or infer missing fields from raw
  validator text.
- Do not expose raw proposal values, validator messages, plan values, state,
  credentials, or signed URLs.
- Do not approve or apply the synthetic customer workload. Keep the plan-only
  run boundary intact.
- Keep the public CloudFormation template-host state and the protected
  control-plane resources outside this PR except for the separately reviewed
  protected release required to test the merged code.
- Preserve protected untracked files and retained evidence artifacts.

## Follow-up work

The resulting hosted plan still needs real regional pricing, supported module
selection for private storage/database/asynchronous work, schema/provider
validation, policy review, and an inspectable exact saved plan before it can
count as the first hosted plan gate.
