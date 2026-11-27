# ticket546 — Make Nova secret references executable as a contract example

PR: #546 (draft)
Branch: `fix/nova-v11-secret-example-546`

## Problem / goal

The v10 prompt fixed resource IDs in the hosted proposal, but the bounded
repair still returned `credential_value` and failed before CodeBuild. Improve
Nova's concrete instruction for the supported database-managed secret and
Lambda reference shape. Keep typed validation and credential rejection intact.

## Current repo and hosted state

- Main `4ecb7070bfa030041dd43958595cb24b5eaff54b` includes PR #545 and is
deployed by plan run `45964473463` and apply run `45965284428`.
- Apply migrations succeeded; all six control-plane Lambdas are Active with
  successful updates and package SHA-256
  `BcFamJkqmrasTs7ngeuGZjAbnqmkuij3qQB2gOTst80=`, matching the versioned
  release package. `https://api.davdeploy.tech/healthz` returned HTTP 200.
- The one authorized retry of hosted run
  `3f27c5fc-75d6-4393-8035-1938035a5a00` used prompt v10, made 2 attempts and
  1 semantic repair, then failed with only the safe `credential_value`
  validation issue. It failed before CodeBuild; no saved plan or workload was
  created. Do not retry this run again.
- The synthetic workload revision remains unapproved and unapplied.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py` defines and checks
  the only supported resource-reference shape, placement, and RDS-managed
  secret output.
- `apps/api/src/davdeploy/terraform_generation.py` defines Nova's task,
  bounded repair feedback, and prompt version.
- Hosted sanitized failure diagnostics are recorded in `docs/test/test546.md`.

## Work planned for the PR

- Give Nova a compact, literal contract example for an RDS-managed master
  secret output and a Lambda `environment[0].variables.*_SECRET_ARN` typed
  reference, including exact JSON keys and allowed placement.
- Make the fixed credential feedback point to the same example and explicitly
  forbid string credentials and arbitrary ARN strings in secret fields.
- Bump the prompt version and add tests that lock the example, version, feedback,
  and security boundaries.
- Deploy through the protected saved-plan workflow, then use a new
  review-only revision to evaluate the v11 prompt. Do not approve or apply the
  synthetic customer workload.

## Acceptance criteria

- [x] Nova receives an unambiguous valid secret-reference example in initial
  generation and bounded correction.
- [x] Credential values and secret references outside the exact typed location
  remain rejected; no validation rule is weakened.
- [x] Raw proposals, credential values, and sensitive plans remain redacted.
- [ ] Focused and required full verification pass; all seven CI checks pass.
- [ ] After protected deployment, a fresh review-only v11 hosted generation
  reaches an inspectable saved plan or reports a bounded actionable failure
  before apply. The workload remains unapproved and unapplied.

## Tests / validation performed

- Hosted v10 retry: 2 attempts, 1 semantic repair, 12,079 input tokens,
  3,119 output tokens, 11,727 ms; estimated cost unavailable. Safe failure:
  `proposal_invalid` with one `credential_value` issue. No CodeBuild run.
- Focused suite: 161 passed, 1 existing Starlette deprecation warning.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv/bin/python` passed:
  config boundary, Ruff, 2,029 tests, OpenAPI snapshot, and Docker Compose
  configuration; 1 existing Starlette deprecation warning.
- GitHub CI, protected deployment, and v11 hosted evidence remain pending.

## Evidence files

- `docs/test/test546.md` — v10 deployed hosted generation retry and outcome.

## Boundaries

- Do not weaken provider schema, typed-reference, account/region, policy, or
  execution boundaries.
- Do not retry run `3f27c5fc-75d6-4393-8035-1938035a5a00` again.
- Do not approve or apply the synthetic customer workload.
- Do not print or persist raw proposals, plan values, tokens, or credentials.

## Follow-up work

- Inspect only safe plan summaries if v11 reaches a saved plan; otherwise
  continue from bounded diagnostics.
- Nova goal completion still requires the full hosted application lifecycle,
  recovery, independent destruction verification, and finite capability matrix.
