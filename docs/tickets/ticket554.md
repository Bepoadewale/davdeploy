# Ticket 554: actionable safe Nova graph validation feedback

## Goal

Improve the bounded Nova repair loop after hosted run `e2395afb-6017-4ceb-9be1-6fdd5661e3c5` failed under prompt v17 with a generic root-level `value_error`. Known contract graph, health, event, and cost validation errors should map to fixed allowlisted categories and guidance without exposing the generated proposal or exception text.

## Current state

Backend main is `38849b326cb3ac6db5a8d96aad4cbcfce66a6fc2` (PR #553). The hosted v17 retry is terminally `FAILED` before CodeBuild, with no saved-plan artifact. Safe diagnostics identify only a generic proposal `value_error`; raw proposal content is not available to this work and must not be retrieved.

## Research and references

- `apps/api/src/davdeploy/terraform_generation.py`: bounded validation feedback and existing `_GRAPH_VALIDATION_FEEDBACK` allowlist.
- `apps/api/src/davdeploy/generated_deployment_contract.py`: deterministic proposal graph, reference, health, event, and cost validators.
- `docs/test/test553.md`: hosted v16 failure and v17 retry boundary.

## Work

- Inventory every known `ValueError` raised by the proposal-level contract validator.
- Add fixed categories and guidance for known causes not already covered.
- Preserve the existing safe root field path and ensure arbitrary exception messages, values, and proposal content are never returned.
- Add regression coverage for every mapped cause, unmapped causes, and feedback sanitization.
- Bump the trusted prompt version only if the revised fixed guidance changes the model contract materially.
- After deployment, create a fresh review-only revision/run and inspect only safe diagnostics or a value-free plan summary.

## Acceptance criteria

- [ ] Every known proposal-level `ValueError` has an intentional safe category/guidance or an explicitly opaque fallback.
- [ ] No arbitrary exception text, generated value, or proposal content is exposed.
- [ ] Focused and full repository verification, docs conventions, and PR CI pass.
- [ ] A fresh deployed plan-only run reaches an inspectable plan or returns actionable bounded feedback; no customer approval/apply occurs.
- [ ] The hosted plan is not claimed to satisfy the first gate unless supported API, private storage, database, async behavior, current regional pricing, and plan policy are actually evidenced.

## Evidence

- `docs/test/test554.md` will record focused/full validation and any later hosted plan-only attempt.

## Boundaries

No customer workload approval, apply, destroy, control-plane state/lock mutation outside the authorized protected release workflow, or access to raw proposal/plan/state values. Preserve protected local files and retained evidence.

## Follow-up

A successful plan-stage artifact still requires explicit support, live pricing, and security/ownership policy review before any approval or apply.
