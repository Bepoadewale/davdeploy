# ticket416 — show pricing assumptions in generated-plan review

PR: #416 https://github.com/Bepoadewale/davdeploy/pull/416
Branch: `feat/plan-review-pricing-assumptions-416`

## Problem / goal

The generated-plan review API exposes S3 `usage_assumptions`, but omits the
revision-bound SQS, RDS backup, serverless and DynamoDB assumptions that feed
the same price evidence. Show every supported assumption field from validated
pricing evidence so the administrator can inspect the quantities behind the
estimate before deciding on the plan.

## Current repo state

- Backend `main` is `2b78e0a97940179bac0654cf005f04df00949995` (PR #415 merged).
- PR #414 pricing is merged source and not deployed. It supports bounded,
  single-region DynamoDB Standard on-demand reads/writes, table storage, and
  PITR assumptions.
- Hosted control plane remains PR #411 source
  `a9c5ca127e8e93845b215c795dd6755e6683869f`, applied in run `43685318088`.
- Draft PR #399 remains open with apply disabled; its apply worker and
  credential broker are incomplete.
- No Nova customer plan or workload has been applied or certified.

## Research / references used

- `apps/api/src/davdeploy/service.py` — `generated_plan_artifact_detail`
  currently projects only generic S3 `usage_assumptions` into review output.
- `apps/api/src/davdeploy/generated_plan_pricing.py` — safe, typed evidence
  fields for S3, SQS, RDS, serverless and DynamoDB assumptions.
- `tests/test_generated_plan_review.py` — artifact persistence, pricing
  display, tenant scope and approval-blocker regressions.
- PR #414 [`ticket414.md`](ticket414.md) and [`test414.md`](../test/test414.md)
  — DynamoDB estimate inputs and support boundary.
- PR #415 [`ticket415.md`](ticket415.md) — immutable revision persistence for
  DynamoDB pricing assumptions.

## Work planned for the PR

1. Project SQS, RDS backup, serverless, and DynamoDB assumptions from validated
   pricing evidence into the generated-plan review response.
2. Preserve the existing S3 field and never source review values from model
   output or unvalidated request data.
3. Add regression coverage showing all revision-bound assumptions are visible
   on the review response and incomplete evidence remains approval-blocking.
4. Update current source/deployment snapshots after PR #415, without implying
   hosted deployment or customer workload proof.
5. Keep PR #399 draft and the hosted apply boundary unchanged.

## Acceptance criteria

- [x] Review output exposes S3, SQS, RDS backup, serverless and DynamoDB
      assumptions only from validated pricing evidence.
- [x] Missing, malformed, or untrusted evidence does not become displayable
      pricing assumptions or make a plan approvable.
- [x] Tests cover revision-bound DynamoDB assumption display and preserve
      existing pricing review behavior.
- [x] Current source, hosted control-plane and PR #399 state is documented
      accurately.
- [x] Focused tests, `make verify`, documentation conventions, diff checks,
      and required GitHub CI pass.
- [x] No hosted deployment, customer workload, runtime flag, or Nova apply
      permission is changed.

## Acceptance status

The review response now returns all supported assumption fields from
digest-validated pricing evidence; the regression test also mutates the stored
DynamoDB assumptions and verifies the untrusted values are hidden and approval
remains blocked. Documentation reflects PR #415 as merged and PR #416 as
source-only. Full verification, documentation checks, and all seven required
GitHub checks pass.

## Tests / validation performed

- `./.venv/bin/python -m pytest -q tests/test_generated_plan_review.py` —
  15 passed (one existing Starlette/httpx deprecation warning).
- `make verify` — passed: 1,254 tests, Ruff, Actions configuration, OpenAPI
  snapshot, and Compose configuration (one existing deprecation warning).
- `python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Required GitHub CI run [`43960105968`](https://github.com/Bepoadewale/davdeploy/actions/runs/43960105968)
  — all seven jobs passed on implementation commit `393ed6912d65ee3d2c3df9113352bee2be8480fa`.

## Evidence files produced

- `docs/tickets/ticket416.md`
- No `docs/test/` customer-workload evidence is planned; this PR is a local API
  review contract change and performs no customer workload.

## Boundaries

This PR updates the plan review response contract and tests only. It does not
deploy PR #414, create a hosted customer plan, change Cloud control-plane
configuration, implement or enable apply, or claim a Nova customer workload.

## Follow-up work

Continue toward a complete authenticated customer plan journey and full cost
evidence. Exact-plan apply and hosted workload lifecycle proof remain gated on
the separate worker, broker and lifecycle requirements.

## Status ledger

- Status: draft; implementation, focused tests, full verification,
  documentation checks, and required CI complete; final evidence update
  awaiting current-head CI before merge.
- Source: branch `feat/plan-review-pricing-assumptions-416` from
  `main` commit `2b78e0a97940179bac0654cf005f04df00949995`.
- Deployed version: none; control plane remains PR #411.
- Current operation: record final-head evidence and complete the reviewed merge.
- Customer workload execution: none.
