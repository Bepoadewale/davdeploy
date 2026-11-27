# ticket549 — Preserve generic sanitized Nova validation feedback

PR: #549 (draft)
Branch: `fix/nova-v13-generic-feedback`

## Problem / goal

The one permitted v12 retry for hosted run
`7ed97bc9-4460-40bb-9ca7-7bf8a84b38b2` failed before CodeBuild with
`proposal_invalid`, but its safe diagnostics contained no validation feedback.
Provide Nova a fixed generic correction when a Pydantic validator produces an
unrecognized error type. Preserve strict validation and never expose raw model
output or validator messages.

## Current repo state

- Main includes PR #547 (merge `03d3192a4e5e5ec2c6b86f0c5abb47c8d2c2bdb4`)
  and PR #548 (merge `aebedcf01b269dff2879e46256457fd2e3895bd5`).
- PR #547 release plan `45981879165` and apply `45982534654` succeeded for
  merge `03d3192a`; migrations completed, all six Lambda packages matched the
  exact release artifact, and `/healthz` returned HTTP 200.
- The single permitted retry of run
  `7ed97bc9-4460-40bb-9ca7-7bf8a84b38b2` used
  `terraform-nova2-contract-v12`. It failed with `proposal_invalid` after 2
  attempts and 1 semantic repair; safe diagnostics had an empty
  `validation_feedback` list. No CodeBuild build, saved plan, or workload was
  created. This run cannot be retried again.
- The existing submitted synthetic revision remains unapproved and unapplied.

## Work planned for the PR

- Preserve a generic safe `invalid` diagnostic rather than dropping an
  unrecognized Pydantic validator code.
- Add fixed allowlisted guidance to regenerate a complete proposal with exact
  field types and allowed values while preserving trusted context.
- Bump the Nova prompt version and test that private validator details never
  appear in model feedback or persisted diagnostics.
- After protected deployment, create a fresh plan-only run for the existing
  submitted revision. Do not approve or apply its workload.

## Acceptance criteria

- [x] Unknown validator codes produce only a generic, fixed
  `invalid`/`proposal` diagnostic and allowlisted guidance.
- [x] Raw validator messages, proposal values, and secrets remain absent from
  feedback and persisted diagnostics.
- [ ] Focused/full local verification and all seven hosted CI checks pass.
- [ ] A fresh v13 hosted run reaches a saved plan or ends with actionable,
  bounded feedback before CodeBuild; the workload remains unapproved and
  unapplied.

## Acceptance status

Hosted v12 failure is recorded. Generic fallback feedback and regression tests
are implemented. Focused and full repository verification pass. PR CI,
protected deployment, and a fresh v13 plan-only run remain pending.

## Tests / validation performed

- Authenticated CLI `/api/v1/me` confirmed workspace administrator access.
- Run status and entity-filtered audit evidence confirmed zero prior explicit
  retries before the single authorized retry was submitted.
- The retry used v12, failed after 2 attempts and 1 semantic repair with
  `proposal_invalid`, and produced no artifact. No customer workload was
  approved or applied.
- Focused generation/run/review suites: 107 passed.
- The regression covers an unrecognized custom validator code with a private
  error message and confirms the generic feedback persists without exposing
  that message, input value, or validator code.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv/bin/python
  PYTHON=python3.12`: config check, lint, all 2,037 tests, OpenAPI snapshot,
  and Docker Compose configuration passed.
- `git diff --check` passed. Hosted PR CI is pending.

## Evidence files produced

- `docs/test/test549.md` — v12 hosted retry and v13 follow-up result.

## Boundaries

- Keep proposal validation, trusted-context binding, account/region checks,
  policy, and execution gates unchanged.
- Do not retry run `7ed97bc9-4460-40bb-9ca7-7bf8a84b38b2` again.
- Never approve or apply the synthetic workload.
- Do not retrieve or log raw proposals, credentials, plan values, or state.

## Follow-up work

Run one fresh hosted plan-only generation after v13 deployment. Inspect only
sanitized diagnostics and a verified review-only artifact. Continue the generic
hosted executor milestone only when the run produces a safe saved plan.
