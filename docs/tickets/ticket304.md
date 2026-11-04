# ticket304 — Reconcile the composed execution baseline

PR: https://github.com/Bepoadewale/davdeploy/pull/304
Branch: `docs/reconcile-composed-execution-baseline`

## Problem / goal

Refresh the execution status and durable goal handoff to match current GitHub,
hosted deployment, API health, and local Terraform-monitor evidence before the
next execution-engine change.

## Current repo state

- Backend main before this PR is `ea9de3a8211b37518205300f8cfd5384c5814f20`
  (PR #303).
- PR #303 is merged and its seven required CI checks passed in run
  [41782907889](https://github.com/Bepoadewale/davdeploy/actions/runs/41782907889).
- Terraform apply [41781326222](https://github.com/Bepoadewale/davdeploy/actions/runs/41781326222)
  succeeded for PR #302 commit `7d087d06aa97df4596e97b4eef7871c70c8a9cc8`,
  before PR #303 merged.
- Live API and worker Lambda packages report successful updates from
  2026-11-04 05:53 UTC. The public `/healthz` route returns the expected
  DavDeploy health response. These checks do not prove a customer workload.
- The local Terraform monitor has no active operation/process. Its historical
  run records are `FINISHED_UNKNOWN_EXIT`; logs and cloud resources still need
  reconciliation before those records can be called successful or clean.
- Frontend PRs #82–#86 are dependency updates and are outside this backend
  execution-baseline reconciliation.

## Research / references used

- `PROJECT_STATUS.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `CODEX_BACKLOG.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- PRs #270, #302, and #303; workflow runs 41671744510, 41781048128,
  41781326222, 41782907889, and 41783453201.

## Work planned for the PR

- Correct stale wording that says PR #303 is open or that PR #302's dispatcher
  input is still rejected.
- Keep the deployment boundary explicit: PR #303's source is merged, but the
  latest hosted Lambda package predates that merge; no composed customer run
  has been performed through it.
- Reconcile PR #270's merge, CI and apply evidence without describing it as
  multi-module customer execution.
- Record the monitor's actual historical uncertainty and current absence of
  active operations without inferring success from missing PIDs.
- Preserve the 26 architecture modules and 30 Terraform implementation entries
  and the full goal scope.

## Acceptance criteria

- [x] GitHub merge/CI and hosted apply evidence are stated with exact IDs.
- [x] Source main and hosted package versions are distinguished.
- [x] API health is described as control-plane health only.
- [x] No active local Terraform mutation is claimed without process evidence.
- [x] `PROJECT_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`,
  `CODEX_BACKLOG.md`, and the two execution-goal documents agree.
- [x] The complete 26-module / 30-implementation scope remains intact.
- [x] Documentation convention and diff checks pass.

## Acceptance status

Pending validation. This PR records facts verified against GitHub, AWS, the
public health endpoint and the local process table. No workload evidence is
claimed.

## Tests / validation performed

`GITHUB_PR_NUMBER=304 python3 scripts/check_doc_conventions.py` passed.
`git diff --check` passed. No runtime test or Terraform mutation was required
for this documentation-only change. The ticket records the read-only GitHub,
AWS, HTTP and local-process observations used for this reconciliation.

## Evidence files produced

No `docs/test/test304.md` is required: this PR changes documentation only and
performs no customer workload operation.

## Boundaries

No application code, infrastructure, customer data, AWS resource, or execution
gate changes in this PR.

## Follow-up work

After this baseline is merged, reconcile the old monitor's uncertain test runs
and remaining disposable resources before claiming their cleanup, then continue
with the next goal step.
