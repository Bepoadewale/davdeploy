# ticket553 — actionable Nova resource ID correction feedback

PR: [#553](https://github.com/Bepoadewale/davdeploy/pull/553) (draft)
Branch: `fix/nova-v17-resource-id-guidance-553`

## Problem / goal

The fresh v16 hosted plan-only run failed before CodeBuild after bounded
generation repair with sanitized `string_pattern_mismatch` feedback at
`resources[*].resource_id`. The v16 prompt already stated the regex and short
examples. Make the correction instruction more concrete while keeping the
contract unchanged, preserving strict validation, and keeping submitted values
out of diagnostics.

## Current repo state

- Backend main is `e8c69f77095d4c0eb08a4a102b2ffde68ba41c71` (PR #552 merged).
- Protected plan `46022153258` and exact saved-plan apply `46023240678`
  deployed v16. The plan had 0 adds, 8 changes, 0 destroys or replacements;
  database migrations succeeded. All six Lambda packages matched the exact
  release ZIP and `/healthz` returned HTTP 200.
- Fresh submitted review revision `9b194ac6-58aa-4ac3-8413-5808949acd87`
  has no decision and retains content digest
  `fb7384977baea8ff63b83d19be71ff5e0fcd54d45b19466a4f79a9722779cd4e`.
- Hosted plan-only run `e2395afb-6017-4ceb-9be1-6fdd5661e3c5` failed as
  `proposal_invalid` with prompt v16, two attempts, one repair, and one safe
  `string_pattern_mismatch` item at `resources[*].resource_id`. It failed
  before CodeBuild; no plan or workload was created.
- The source architecture still has unsupported execution modules and
  fixture-only pricing. This diagnostic run does not satisfy the first hosted
  plan gate.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py` — strict resource
  ID pattern and graph/reference validation.
- `apps/api/src/davdeploy/terraform_generation.py` — trusted generation prompt,
  prompt version, and safe fixed feedback.
- `docs/test/test552.md` — v15/v16 hosted attempts and safe diagnostic boundary.

## Work planned for the PR

1. [x] Describe `resource_id` as a short machine key, provide a fixed vocabulary of
   common IDs, and specify a numeric suffix for duplicate roles.
2. [x] Repeat the exact 24-character lowercase/digit/hyphen limit and separate
   `resource_id` from the Terraform `name` field.
3. [x] Keep the contract pattern, reference rules, and validation strict.
4. [x] Test prompt instructions, sanitized pattern feedback, and absence of raw
   invalid IDs or validator text.
5. Bump the prompt version to v17. After protected deployment, retry the failed
   v16 run at most once with a fresh idempotency key and inspect only bounded
   diagnostics or a sanitized plan artifact summary.

## Acceptance criteria

- [x] Fixed ID guidance provides short role IDs and a valid duplicate suffix.
- [x] Prompt states the exact regex, max length, forbidden characters, and
      separation from Terraform names.
- [x] Invalid IDs still fail before CodeBuild; raw values/messages remain
      absent from public diagnostics and repair context.
- [x] Focused tests, full local verification, and docs checks pass locally.
- [ ] All required final-head CI checks pass.
- [ ] One authorized retry of the v16 run after v17 deployment returns
      actionable safe feedback or inspectable saved-plan evidence. No workload
      approval or apply occurs.

## Acceptance status

Draft opened at bootstrap commit `067a7596`. Implementation commit
`1e11e594cb4cc510f467813c7f7d39739a55677f`
adds a fixed vocabulary and suffix rule for stable resource IDs, repeats the
exact regex and forbidden characters, and raises the prompt version to v17.
Focused tests (126), full verification (2,056 tests plus Ruff, Actions
configuration, OpenAPI snapshot, and Compose checks), documentation conventions,
and diff checks pass locally. PR CI, protected deployment, and the single
authorized hosted retry remain pending.

## Tests / validation performed

- Authenticated `/api/v1/me` returned HTTP 200 and role `administrator` after
  the v16 deployment.
- The v16 hosted run's bounded diagnostics were recorded without fetching raw
  proposal text, submitted values, or validator messages.
- `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest
  tests/test_terraform_generation.py tests/test_customer_plan_review.py
  tests/test_nova_plan_runs.py -q` — 126 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python` —
  passed: 2,056 tests, Ruff, Actions configuration, OpenAPI snapshot, and Docker
  Compose configuration. One existing Starlette deprecation warning.
- Focused Ruff, `GITHUB_PR_NUMBER=553 .../python scripts/check_doc_conventions.py`,
  and `git diff --check` — passed.
- Required PR CI is pending for the final pushed head.

## Evidence files produced

- `docs/tickets/ticket553.md`
- `docs/test/test553.md`

## Boundaries

- Do not change the proposal schema or weaken validation.
- Do not expose raw model output, invalid values, validator messages, saved
  plan bytes, Terraform state, credentials, or signed URLs.
- Keep the run plan-only. Never approve or apply the synthetic workload.
- Preserve fixture-pricing and unsupported-module limitations; do not claim a
  successful customer plan or workload certification without evidence.
- Preserve protected untracked files and retained artifacts.

## Follow-up work

The first hosted acceptance gate still requires a supported proposal with
private storage, a real database, asynchronous work, current regional pricing,
exact plan policy, and an inspectable saved plan.
