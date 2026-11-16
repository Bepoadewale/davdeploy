# ticket415 — verify DynamoDB pricing assumptions persist by revision

PR: #415 https://github.com/Bepoadewale/davdeploy/pull/415
Branch: `fix/dynamodb-pricing-assumption-lifecycle-415`

## Problem / goal

PR #414 adds strict DynamoDB cost assumptions to the customer-plan constraint
contract and persists them through a new immutable plan revision. The focused
pricing tests verify math and digest binding, but no lifecycle regression test
currently proves that the assumptions are stored on only the new revision,
appear in its diff and workload spec, and can be cleared in a later revision.
Add that regression coverage and reconcile the current source-versus-hosted
status after PRs #413 and #414 merged.

## Current repo state

- Backend `main` is `373b82a7011a54b046820f7990065bcfc017beac` (PR #414 merge).
- PR #414 is merged source; it is not deployed. Hosted control plane remains
  PR #411 commit `a9c5ca127e8e93845b215c795dd6755e6683869f`, applied by run
  `43685318088`.
- PR #399 remains draft at `8dbd08976940e1747e28be4a9fcbfe53d68b6844`, with
  apply disabled and its executable Terraform worker and broker incomplete.
- No Nova customer plan or workload has been applied or certified.
- The AWS test inventory has no SageMaker endpoint/model/configuration; four
  tagged Batch job definitions are inactive. The SageMaker lineage action,
  context, and artifact association remain as audit evidence.
- Local protected untracked `--only-show-errors` and `.venv-pr399/` are retained.

## Research / references used

- `apps/api/src/davdeploy/service.py` — immutable constraint revision storage
  and revision diff generation.
- `apps/api/src/davdeploy/domain.py` — strict customer-plan constraint fields.
- `tests/test_infrastructure_plan_lifecycle.py` — existing S3, SQS, RDS, and
  serverless pricing-assumption lifecycle regressions.
- `docs/product/COMPOSED_EXECUTION_GOAL.md` — Nova plan, approval, apply, health,
  and lifecycle acceptance boundary.
- PR #414 [`ticket414.md`](ticket414.md) and [`test414.md`](../test/test414.md)
  — source-only DynamoDB pricing evidence and limits.

## Work planned for the PR

1. Add a lifecycle test for DynamoDB assumptions on a new immutable revision,
   including `user_constraints`, workload spec, revision diff, and digest.
2. Verify clearing assumptions creates another revision and does not mutate
   earlier revision contents.
3. Update current source/hosted snapshots and PR #414's ticket/evidence to
   reflect merges `de873ef` (#413) and `373b82a` (#414) without implying hosted
   deployment or customer workload proof.
4. Keep PR #399 draft and all hosted runtime/apply controls unchanged.

## Acceptance criteria

- [x] DynamoDB assumptions validate and persist only in a new immutable plan
      revision.
- [x] The assumptions appear in the new revision's workload spec and revision
      diff, and the revision digest binds them.
- [x] Clearing assumptions creates a later revision and preserves prior
      revision contents.
- [x] Current source, hosted control-plane, PR #399, PR #413, PR #414, and AWS
      evidence status is documented accurately.
- [ ] Focused tests, `make verify`, documentation conventions, diff checks,
      and required GitHub CI pass.
- [x] No hosted runtime flags, customer workload, control-plane deployment, or
      Nova apply permission is changed.

## Acceptance status

The lifecycle regression now covers new-revision storage, workload-spec
propagation, revision diff and digest binding, clearing in a later revision,
and preservation of prior revision contents. The current source and hosted
status docs now identify PR #414 as merged source, PR #411 as deployed, and
PR #399 as a draft with apply still disabled. Local validation and documentation
checks are complete; hosted CI remains pending.

## Tests / validation performed

- `./.venv/bin/python -m pytest -q tests/test_infrastructure_plan_lifecycle.py`
  — 13 passed (one existing Starlette/httpx deprecation warning).
- `make verify` — passed: 1,254 tests, Ruff, Actions configuration, OpenAPI
  snapshot, and Compose configuration (one existing deprecation warning).
- `python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Required GitHub CI — pending.

## Evidence files produced

- `docs/tickets/ticket415.md`
- No `docs/test/` customer-workload record is planned: this PR runs local
  lifecycle regression tests only and performs no customer workload.

## Boundaries

This PR is source verification and status documentation only. It does not
deploy PR #414, connect the hosted customer plan workflow, implement or enable
the PR #399 apply path, mutate AWS resources, or claim Nova customer execution.
Do not delete the retained SageMaker lineage records or protected local files.

## Follow-up work

Continue toward an authenticated customer plan journey and complete cost
evidence. The separately gated exact-plan apply and lifecycle proof remain
blocked until the worker, credential broker, and hosted customer lifecycle are
implemented and verified.

## Status ledger

- Status: draft; lifecycle verification, status reconciliation, and local checks
  complete; hosted CI pending.
- Source: branch `fix/dynamodb-pricing-assumption-lifecycle-415` from
  `main` commit `373b82a7011a54b046820f7990065bcfc017beac`.
- Deployed version: none; control plane remains PR #411.
- Current operation: wait for required GitHub checks, then update the acceptance
  status before marking the PR ready.
- Customer workload execution: none.
