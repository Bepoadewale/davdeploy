# ticket545 — Strengthen Nova secret and resource ID guidance

PR: #545 (draft)
Branch: `fix/nova-v10-guidance-545`

## Problem / goal

The deployed v9 prompt's bounded repair still produced unsafe credential fields
and malformed resource IDs for the same submitted synthetic application. Make
the accepted secret-reference shape and short-ID format concrete in the task
and fixed feedback, without weakening validation.

## Current repo state

- Main `668b90d7a7a9516913891667bb3c4dc27353f34c` includes PR #544 and is
  deployed by protected plan `45959933980` and apply `45960596382`.
- Fresh v9 plan-only run `3f27c5fc-75d6-4393-8035-1938035a5a00` failed before
  CodeBuild after 2 attempts and 1 repair. Safe diagnostics returned
  `credential_value` and `string_pattern_mismatch` issue categories. No plan or
  workload exists.
- This v9 run has not had an explicit retry. It may be retried once after v10
  is deployed. Do not retry the earlier failed v8 run.

## Research / references used

- Typed secret reference schema and placement rules in
  `apps/api/src/davdeploy/generated_deployment_contract.py`.
- Bounded generation prompt and safe feedback in
  `apps/api/src/davdeploy/terraform_generation.py`.
- Hosted v9 failure evidence in `docs/test/test545.md`.

## Work planned for the PR

- Give an exact JSON shape for `resource_reference` and restrict its placement
  to supported Lambda secret ARN variables.
- Name short, valid resource ID examples and explicitly prohibit underscores,
  uppercase, and IDs over 24 characters in fixed feedback.
- Bump the prompt version to v10 and add regression tests for prompt content,
  exact guidance, and allowlist boundaries.
- After merge and protected deployment, retry the v9 run once with a new
  idempotency key; no customer approval or apply.

## Acceptance criteria

- [ ] Credentials and malformed IDs receive specific fixed, allowlisted
  guidance in the repair loop and hosted diagnostics.
- [ ] Raw causes, input values, generated proposal text, and secrets remain hidden.
- [ ] Focused tests, full verification, docs checks, and required CI pass.
- [ ] The one post-deployment v10 retry produces an inspectable plan or a
  bounded actionable failure before CodeBuild. No customer workload is applied.

## Acceptance status

Implementation is in progress. Tests, CI, protected deployment, and the v10
retry are pending. The workload remains unapproved and unapplied.

## Tests / validation performed

- Local validation: pending.
- Hosted CI: pending.

## Evidence files produced

- `docs/test/test545.md` — v9 safe failure and post-deployment retry outcome.

## Boundaries

- Do not relax typed validation, provider/account/region checks, or plan policy.
- Do not retry the failed v8 run or retry v9 more than once.
- Never approve or apply the synthetic customer workload.
- Never print or persist raw proposals, plan values, or credentials.

## Follow-up work

- Inspect exact plan scope and cost evidence if the retry reaches a validated
  saved plan; otherwise continue from bounded diagnostics only.
- The Nova goal remains incomplete until hosted apply, behavior, lifecycle,
  recovery, destruction, and finite matrix gates are evidenced.
