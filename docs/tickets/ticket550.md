# ticket550 — Make Nova graph validation feedback specific and safe

PR: #550 (draft)
Branch: `fix/nova-v14-graph-feedback`

## Problem / goal

The fresh v13 hosted run failed with a proposal graph `value_error`. The
sanitized diagnostics retained only broad graph guidance. Map known graph
validator causes to distinct fixed issue codes and correction guidance so Nova
can repair the exact class of graph error without exposing raw validator text.

## Current repo state

- Main includes PR #549, merged as
  `e8fc9ab8f391f22d889a119e9e3a64a47d4db09f`.
- Protected plan `45991858852` and apply `45992221348` deployed v13. The saved
  plan had eight in-place changes, zero adds/destroys/replacements. Migration
  verification passed, all six Lambda hashes matched the release artifact,
  and `/healthz` returned HTTP 200.
- Fresh submitted review revision
  `fafb7ec2-2173-4ce8-a191-0b5a93a448d6` produced run
  `71ce7def-79ec-4128-adf3-e2de6973354e`. It failed with
  `NOVA_GENERATION_FAILED` after 2 attempts and 1 semantic repair, using
  `terraform-nova2-contract-v13`. Safe feedback identified only
  `value_error` at `proposal` with the generic resource-graph guidance. No
  CodeBuild build, saved plan, or workload artifact was created.
- A new-run request for the prior revision was deduplicated to its existing
  failed run. It did not create another run or model attempt. The v11 run's
  explicit retry limit remains exhausted.
- No customer workload has been approved or applied.

## Research / references used

- Graph validator causes and fixed feedback in
  `apps/api/src/davdeploy/terraform_generation.py`.
- Pydantic error sanitization and persisted generation diagnostics in
  `apps/api/src/davdeploy/terraform_generation.py`,
  `apps/api/src/davdeploy/service.py`, and `apps/api/src/davdeploy/main.py`.
- Authenticated hosted status for run
  `71ce7def-79ec-4128-adf3-e2de6973354e`.

## Work planned for the PR

- Map each known dependency, ID uniqueness, address uniqueness, typed
  reference, output type, and health-target cause to a distinct allowlisted
  issue and fixed instruction.
- Keep unknown graph causes on the existing generic safe guidance.
- Preserve strict graph validation and bump the prompt version.
- Create a new submitted review-only revision after protected deployment and
  run v14 once. Do not approve or apply the workload.

## Acceptance criteria

- [x] Known graph causes produce their exact safe issue code and fixed guidance.
- [x] Unknown causes, raw messages, proposal values, and secrets remain
  redacted from repair prompts and persisted diagnostics.
- [ ] Graph constraints remain strict; no invalid graph reaches CodeBuild.
- [x] Focused/full local verification and all seven hosted CI checks pass.
- [ ] One fresh v14 hosted run reaches a saved plan or returns actionable,
  bounded feedback before CodeBuild. No approval or workload apply occurs.

## Acceptance status

The v13 graph failure is recorded. Distinct allowlisted issue codes and fixed
guidance for all known graph causes are implemented with regression tests.
Focused and full repository verification pass. All seven checks in PR run
`45995049620` pass. Protected deployment and the fresh v14 run remain pending.

## Tests / validation performed

- Verified the v13 run's bounded status and allowlisted `value_error` / `proposal`
  diagnostic. No raw proposal or validator message was retrieved.
- The v11 failed run remains out of retries. The v13 failed run is also not
  reused; request deduplication is bound to its submitted revision.
- Focused generation/run/review suites: 114 passed.
- Regression tests cover all seven known graph causes and ensure each maps to
  distinct fixed guidance without reproducing the validator message.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv/bin/python
  PYTHON=python3.12`: config check, lint, all 2,044 tests, OpenAPI snapshot,
  and Docker Compose configuration passed.
- `git diff --check` passed. PR CI run `45995049620` passed all seven checks.

## Evidence files produced

- `docs/test/test550.md` — v13 hosted graph failure and v14 follow-up.

## Boundaries

- Keep proposal schema, trusted revision/region/account binding, policy, and
  runner execution boundaries unchanged.
- Do not retry v11 run `7ed97bc9-4460-40bb-9ca7-7bf8a84b38b2`.
- Do not request another run for v13 revision
  `fafb7ec2-2173-4ce8-a191-0b5a93a448d6`.
- Never approve or apply the synthetic workload.
- Keep raw proposals, credentials, plan values, state, and validator messages
  out of output and diagnostics.

## Follow-up work

Create one new plan-only run against a newly submitted review revision after
v14 is deployed. Inspect only allowlisted diagnostics and review-only artifact
evidence.
