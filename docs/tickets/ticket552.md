# ticket552 — actionable Nova health payload validation feedback

PR: [#552](https://github.com/Bepoadewale/davdeploy/pull/552) (draft)
Branch: `fix/nova-v16-health-payload-552`

## Problem / goal

The first v15 hosted plan-only generation run failed before CodeBuild with two
bounded `invalid` diagnostics at `health_assertions[*].payload_size_bytes`.
Local contract reproduction identified the rejected value `4097` only in a
synthetic fixture: Pydantic reports `less_than_equal` because the contract caps
storage and queue payload sizes at 4096 bytes. Make this failure actionable
with deterministic feedback and prompt guidance while preserving the strict
contract and sanitization boundary.

## Current repo state

- Backend main is `6f6a1c1e42645327b5ce30006d1f8be39179561f` (PR #551 merged).
- Prompt v15 is deployed. Protected plan `46016249082` and exact saved-plan
  apply `46017348420` succeeded for this commit. Terraform reported 0 adds, 8
  changes, 0 destroys; migrations succeeded; all six Lambda package hashes
  matched the versioned release; `/healthz` and authenticated administrator
  `/api/v1/me` returned HTTP 200.
- Hosted plan-only run `7f3eeb66-d8ba-4dae-a097-e1d68ca9fd8e` used prompt v15
  and failed as `proposal_invalid` after two attempts and one repair. Safe
  feedback contained two `invalid` items for
  `health_assertions[*].payload_size_bytes`. It failed before CodeBuild; no
  artifact or Terraform plan was created.
- The synthetic source architecture still has unsupported execution modules
  and fixture-only cost data. This run is feedback diagnosis only, not the
  first hosted-plan acceptance gate.
- Review revision `6b542c95-d3c6-4b48-909e-293b4effeff1` is `SUBMITTED`, has
  no decision, and retains content digest
  `fb7384977baea8ff63b83d19be71ff5e0fcd54d45b19466a4f79a9722779cd4e`.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py` — storage/queue
  `payload_size_bytes` range and assertion-specific schema.
- `apps/api/src/davdeploy/terraform_generation.py` — Pydantic error allowlist,
  canonical path sanitizer, fixed feedback guidance, and prompt version.
- `docs/test/test551.md` — v15 hosted diagnostic and deployed code evidence.
- Pydantic `less_than_equal` feedback is safe to expose only as a fixed code,
  schema-derived field path, and trusted fixed guidance. Never include the
  rejected value, validator message, or proposal content.

## Work planned for the PR

1. [x] Add the stable `less_than_equal` validator code to the safe allowlist.
2. [x] Provide fixed guidance for `health_assertions[*].payload_size_bytes`:
   integer 1–4096 and only for `storage_roundtrip` or `queue_roundtrip`.
   Explain that `inference_response` uses `minimum_response_bytes` instead.
3. [x] Extend the trusted Nova generation task with assertion-specific payload
   fields and bounds without relaxing schema validation.
4. [x] Add tests for upper/lower bounds, assertion-kind applicability, safe
   diagnostics, and raw-value/message redaction. Preserve pre-CodeBuild rejection.
5. After protected deployment, create a fresh submitted review-only revision
   and run one v16 plan-only generation request. Inspect only bounded
   diagnostics or a safe artifact summary; do not approve or apply a workload.

## Acceptance criteria

- [x] `less_than_equal` is reported only through the fixed safe code allowlist.
- [x] Health payload guidance identifies the applicable assertion kinds and
  exact 1–4096 range without exposing submitted values.
- [x] Out-of-range and wrong-kind payload fields still fail typed validation
  before CodeBuild.
- [ ] Focused tests, full local verification, documentation checks, and all
  required final-head PR CI checks pass.
- [ ] One fresh v16 plan-only run returns actionable bounded feedback or
  inspectable saved-plan evidence; no workload approval/apply occurs.

## Acceptance status

The v15 hosted diagnostic and local synthetic reproduction are recorded.
Implementation commit `c5b6d3fc4051e7ce6ad762a353b19a49a5afb79e` adds fixed
field guidance, includes
`less_than_equal` in the safe error-code allowlist, and increments the trusted
prompt version to v16. Focused tests (125 across generation, review, and run
diagnostics), full verification (2,055 tests plus Ruff, Actions configuration,
OpenAPI snapshot, and Compose checks), documentation conventions, and diff
checks pass locally. PR CI, protected v16 deployment, and the fresh hosted v16
run remain pending.

## Tests / validation performed

- Read-only hosted status verified the prior v14 run remained terminally
  `FAILED` and its review remained submitted and undecided.
- Current v15 run `7f3eeb66-d8ba-4dae-a097-e1d68ca9fd8e` was queued from a fresh
  review-only revision. It failed before CodeBuild; safe diagnostics only were
  retrieved.
- Local Pydantic reproduction with synthetic payload size `4097` confirmed
  `less_than_equal` at the health payload field. No real proposal value was
  inspected.
- `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest
  tests/test_terraform_generation.py tests/test_customer_plan_review.py
  tests/test_nova_plan_runs.py -q` — 125 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python` —
  passed: 2,055 tests, Ruff, Actions configuration, OpenAPI snapshot, and Docker
  Compose configuration. One existing Starlette deprecation warning.
- Focused Ruff, `GITHUB_PR_NUMBER=552 .../python scripts/check_doc_conventions.py`,
  and `git diff --check` — passed.
- PR CI is required on the final pushed head; the bootstrap-only draft run
  failed docs conventions because its ticket had not yet been pushed.

## Evidence files produced

- `docs/tickets/ticket552.md`
- `docs/test/test552.md`

## Boundaries

- Do not change the typed contract, thresholds, model authorization, plan
  policy, or execution permissions.
- Do not retrieve or expose the raw proposal, submitted values, full Pydantic
  errors, raw saved plan, state, credentials, or signed URLs.
- Keep the run plan-only. Do not approve or apply the synthetic workload.
- Preserve unsupported-module and fixture-pricing limitations; do not claim a
  valid hosted plan or customer workload certification without evidence.
- Keep protected untracked files and retained artifacts untouched.

## Follow-up work

The first hosted-plan gate still requires supported private storage, a real
database and asynchronous work, current regional pricing, exact plan policy,
and an inspectable saved plan. A successful v16 validation repair alone will
not satisfy those requirements.
