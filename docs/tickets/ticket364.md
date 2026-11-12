# ticket364 — reconcile Nova policy and plan-history status evidence

PR: [#364](https://github.com/Bepoadewale/davdeploy/pull/364) (draft)
Branch: `docs/reconcile-nova-dynamodb-policy-364`

## Problem / goal

Bring backend status and readiness documents into line with merged PR #363 and current frontend PR #102. State clearly that DynamoDB recovery checks are merged in backend source but not deployed, and that plan-history/run-status presentation exists only on an unmerged frontend draft.

## Current repo state

Backend `main` is `4d5997c45c2858c4d5f5b9151ebf793d685f5353`; merged-main CI `43123201873` passed all seven jobs. Backend control-plane deployment has not been run for #363. Nova runner, state API, plan reviews, customer-role verification, and customer execution remain disabled. Frontend PR #102 is open as a draft, not deployed; it now loads tenant-scoped paginated project revision history and latest Nova run state.

## Research / references used

- Backend current source/evidence: `docs/test/test363.md`, `docs/tickets/ticket363.md`, `PROJECT_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/product/EXECUTION_READINESS_MATRIX.md`, and `CODEX_BACKLOG.md`.
- Frontend draft evidence: `Bepoadewale/davdeploy-frontend` PR #102 and its `docs/tickets/ticket102.md` / `docs/test/test102.md` on branch `fix/customer-facing-surface-audit-102`.

## Work planned for the PR

- Reconcile current backend deployment/source status and policy summary.
- Add #363 to the generated-plan security record and make no deployment claim for it.
- Correct stale wording that the customer history UI has not integrated backend history/run APIs, while stating that PR #102 remains draft and local-fixture validated only.
- Preserve historical evidence, capability counts and all existing customer/availability claims.

## Acceptance criteria

- [x] Backend status documents identify #363 as merged source and not deployed.
- [x] Frontend #102 is described as draft/unmerged and not deployed, with plan-history/run-status API integration marked implemented only in that branch.
- [x] No pricing, hosted approval/apply, health, recovery, teardown or composed certification capability is overstated.
- [x] Documentation conventions and `git diff --check` pass.
- [ ] All seven required GitHub checks pass and current-head review finds no blocker.

## Acceptance status

- Implementation and local documentation validation are complete; final-head CI/review remain pending.

## Tests / validation performed

- `.venv/bin/python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.

## Evidence files produced

- None. Documentation-only PR; runtime evidence is not applicable.

## Boundaries

- This PR changes no runtime code, feature flags, customer APIs or infrastructure.
- Keep PR #102 as a draft; do not merge, deploy or alter the frontend in this PR.

## Follow-up work

- Continue with the next dependency-ready Nova security/execution gate after this reconciliation.
