# ticket316 Reconcile Nova execution status documentation

PR: #316 (draft)
Branch: docs/nova-execution-status-316

## Problem / goal

The execution-readiness matrix and historical ticket records lag behind merged
Nova planning work. The matrix also pointed readers to a missing, obsolete
renderer-by-renderer goal and could make the current enabled App Runner path
look disabled.

## Current repo state

PR #313 is closed unmerged. PRs #314 and #315 are merged, but a read-only AWS
check shows their source changes are not in the live Lambda release. Existing
App Runner execution remains the only enabled customer renderer; Nova's saved
plan and approval path is not connected to the hosted worker.

## Research / references used

- Backend PR #313: https://github.com/Bepoadewale/davdeploy/pull/313
- Backend PR #314: https://github.com/Bepoadewale/davdeploy/pull/314
- Backend PR #315: https://github.com/Bepoadewale/davdeploy/pull/315
- AWS Lambda `GetFunctionConfiguration`: https://docs.aws.amazon.com/lambda/latest/api/API_GetFunctionConfiguration.html

## Work planned for the PR

Reconcile ticket #313 as closed unmerged and superseded, record merged and
verified evidence for #314 and #315, update the execution-readiness matrix
with source-versus-deployed status, and point its active work sequence at the
Nova plan, approval, hosted execution, recovery, and certification gates.

## Acceptance criteria

- [x] The matrix identifies source main at PR #315 and distinguishes it from
  the last read-only-verified hosted Lambda release.
- [x] The matrix describes #311-#315 Nova plan capabilities accurately and
  states that hosted generation/apply remains unavailable.
- [x] The matrix identifies App Runner as the only enabled customer renderer
  and labels old per-renderer tasks as compatibility work.
- [x] Ticket #313 is marked closed unmerged and superseded by #314.
- [x] Tickets #314 and #315 record their merge, CI, test evidence, and deployment
  boundaries.
- [x] Documentation convention and diff checks pass.
- [ ] Required GitHub CI passes and the PR is merged.

## Acceptance status

Implementation and local documentation checks are complete. GitHub CI and
merge are pending.

## Tests / validation performed

- `python3 scripts/check_doc_conventions.py` passed.
- `git diff --check` passed.
- This is documentation-only; no application test suite or AWS mutation was
  run for this PR.

## Evidence files produced

- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/tickets/ticket313.md`
- `docs/tickets/ticket314.md`
- `docs/tickets/ticket315.md`
- `docs/test/test316.md`

## Boundaries

This PR changes no application behavior, AWS infrastructure, worker, renderer,
or customer execution setting. The Nova plan path remains undeployed and plan-
only; live customer workload execution is still not generally available.

## Follow-up work

Implement real regional price and budget evidence, complete ownership and safe
reference policy, connect the Nova plan-only runner to the hosted worker, then
build exact-plan apply, health, recovery, and cleanup evidence.
