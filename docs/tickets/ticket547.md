# ticket547 — Clarify Nova Terraform resource names

PR: #547 (draft)
Branch: `fix/nova-v12-resource-name-547`

## Problem / goal

The deployed v11 prompt resolved the `credential_value` failure, but hosted
Nova generation now returns a `string_pattern_mismatch` for
`resources[*].name`. Clarify the contract distinction between stable resource
IDs and Terraform's local resource names. Keep the schema and validation strict.

## Current repo state

- Main `a0b06dc2debde3bc17caeb42699476556e9bb825` includes PR #546 and is
deployed by protected plan `45973303637` and apply `45974135992`.
- Main CI `45972809624` and PR #546 final CI `45972128239` passed all seven
  checks. Migrations completed; all six Lambda packages match the exact v11
  release and are Active/Successful. API health returned HTTP 200.
- Fresh hosted run `7ed97bc9-4460-40bb-9ca7-7bf8a84b38b2` used v11, made 2
  attempts and 1 semantic repair, then failed before CodeBuild with one safe
  `resources[*].name` `string_pattern_mismatch`. No build, plan, or workload
  exists. This run has not been explicitly retried and may be retried once
  after v12 is deployed.
- Its submitted revision remains `UNEXECUTED_APPROVAL_ONLY`; no customer
  approval or workload apply has occurred.

## Research / references used

- `GeneratedResource.name` and `resource_id` patterns in
  `apps/api/src/davdeploy/generated_deployment_contract.py`.
- Prompt, validation feedback, and canonical field paths in
  `apps/api/src/davdeploy/terraform_generation.py`.
- Sanitized hosted diagnostics in `docs/test/test547.md`.

## Work planned for the PR

- State the exact `name` pattern and contrast it directly with the hyphenated
  `resource_id` pattern in the generation task.
- Give paired examples such as `resource_id=db-primary` with
  `name=primary_database`; tell Nova not to copy one field into the other.
- Add fixed allowlisted feedback for `resources[*].name` pattern errors.
- Bump the prompt version and test both initial instructions and feedback.
- After protected deployment, retry hosted run
  `7ed97bc9-4460-40bb-9ca7-7bf8a84b38b2` once. Do not approve or apply the
  synthetic workload.

## Acceptance criteria

- [x] Nova receives an explicit distinct pattern and paired examples for
  `resource_id` versus Terraform `name` in generation and repair.
- [x] Invalid resource names remain rejected; no validation is weakened.
- [x] Sanitized feedback identifies only the safe canonical field and fixed
  guidance; raw proposals remain hidden.
- [x] Focused/full local verification and all seven hosted CI checks pass.
- [ ] After protected deployment, the one v12 retry reaches a saved plan or a
  bounded actionable failure before apply. The workload remains unapproved and
  unapplied.

## Acceptance status

Hosted v11 evidence is recorded. Prompt/feedback changes and regression tests
are implemented. Focused tests, full repository verification, and all seven
checks in PR run `45979757789` pass. Protected deployment and the one
post-deployment retry remain pending.

## Tests / validation performed

- Hosted v11 run: `proposal_invalid`, 2 attempts, 1 semantic repair, 12,404
  input tokens, 4,057 output tokens, 15,860 ms; estimated cost unavailable.
  Safe feedback contained only the resource-name pattern mismatch. No CodeBuild
  run.
- Focused generation/run/review suites: 106 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv/bin/python
  PYTHON=python3.12`: config check, lint, all 2,030 tests, OpenAPI snapshot,
  and Docker Compose configuration passed.
- `git diff --check` passed. PR CI run `45979757789` passed all seven checks.

## Evidence files produced

- `docs/test/test547.md` — v11 deployed hosted-generation failure and v12
  follow-up result.

## Boundaries

- Keep schema, account/region binding, provider checks, policy, and execution
  boundaries unchanged.
- Do not retry run `7ed97bc9-4460-40bb-9ca7-7bf8a84b38b2` more than once.
- Do not approve or apply the synthetic customer workload.
- Never retrieve or log raw proposal text, credentials, plan values, or state.

## Follow-up work

- Inspect only safe plan summaries if v12 reaches a saved plan; otherwise use
  bounded diagnostics to select the next corrective implementation.
- Full hosted workload behavior, lifecycle, recovery, destruction, and matrix
  evidence remain unmet.
