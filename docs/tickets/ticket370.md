# ticket370 — reconcile current Nova role-verification status

PR: #370  
Branch: `docs/reconcile-plan-role-status-370`

## Problem / goal

After PR #369 deployed the Nova plan-role trust/account verification gate,
several documents still described that gate as disabled and cited older
source/deployment versions as current. Reconcile current status while
preserving dated release snapshots as historical evidence.

## Current repo state

- Backend `main` is `aa1a9a820a719d0a53dcd6c7ff5ff96ab7f06250` after docs PR #369.
- Runtime source commit `8cebf39f700309fbb57c1b307c18026204be844d` is deployed
  via protected plan `43144381303` and exact saved-plan apply `43145180803`,
  deployment `7727105514`.
- Only plan-role trust/account verification is enabled. Runner, broker, plan
  review, state API, and hosted certification remain disabled.
- No `davdeployPlan-*` role exists in AWS account `654654474502`; no customer
  role permissions or Nova workload have been verified.
- Pricing PR #318 remains held; exact-cost approval is unavailable.

## Research / references used

- `docs/test/test369.md` and merged PR #369.
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `PROJECT_STATUS.md`
- `CODEX_BACKLOG.md`
- Read-only AWS Lambda configuration and IAM role-name query.

## Work planned for the PR

- [x] Update the project and implementation summaries with exact current
  source and hosted release state.
- [x] Correct stale role-verification gate descriptions in the matrix while
  retaining dated snapshots as history.
- [x] Preserve the distinction between trust/account identity and effective
  permission verification.
- [x] Record the documentation audit and validation evidence.

## Acceptance criteria

- [x] Current docs identify backend main and deployed runtime commit accurately.
- [x] Current docs say plan-role trust/account verification is enabled, while
  customer role installation/effective permissions are still unverified.
- [x] Current docs keep plan runner, broker, reviews, state API, hosted
  certification, pricing, approval, apply, lifecycle and certification gaps
  explicit.
- [x] Dated prior deployment records remain intact and are labeled historical.
- [x] No private goal, credential guidance, or customer data is copied into the
  repository.
- [x] All seven required GitHub checks passed on implementation head
  `3c3a11130358684026b728d451ce57f12bb1d63e` in run `43148509141`; the final
  evidence head's checks are recorded below.

## Acceptance status

- [x] Documentation updates and exact-state review complete.
- [x] Documentation convention and whitespace checks pass.
- [x] CI run `43148983714` passed all seven jobs on head
  `b7efe7906c4f23c700ca14a6b30e3a34caef8c6b`.
- [ ] PR reviewed and merged only after final-head checks pass.

## Tests / validation performed

Read-only evidence review only; no workload or infrastructure mutation is part
of this PR.

- `python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- GitHub Actions run
  [43148509141](https://github.com/Bepoadewale/davdeploy/actions/runs/43148509141)
  passed all seven required jobs on head
  `3c3a11130358684026b728d451ce57f12bb1d63e`.
- GitHub Actions run
  [43148983714](https://github.com/Bepoadewale/davdeploy/actions/runs/43148983714)
  passed all seven required jobs on head
  `b7efe7906c4f23c700ca14a6b30e3a34caef8c6b`. The ticket update must pass
  CI on the resulting final head before merge.

## Evidence files produced

- `docs/test/test370.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `PROJECT_STATUS.md`
- `CODEX_BACKLOG.md`

## Boundaries

Documentation only. Do not enable any additional Nova gate, install a customer
role, run a plan, or change the held pricing decision in this PR.

## Follow-up work

Use an authenticated workspace-admin session to install and verify a plan role
when available. Continue tenant-scoped remote state and other independent Nova
work; keep pricing approval blocked until account-owner direction and trusted
complete regional evidence are available.
