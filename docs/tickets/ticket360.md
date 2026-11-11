# ticket360 — reconcile Nova source and hosted release evidence

PR: [#360](https://github.com/Bepoadewale/davdeploy/pull/360) (draft; number reserved)
Branch: `docs/reconcile-nova-release-360`
Base: `main`

## Problem / goal

Reconcile Nova source, hosted release status, and the finite execution-readiness
matrix using exact PR, commit, plan, apply, and runtime evidence. Keep deployed
control-plane code distinct from disabled customer planning and lifecycle.

## Current repo state

- Backend `main` is `d734547a0551e85c5eafcc7349561e3ea7790589` (PR #359); this
  commit is now deployed by protected plan `43098415855` and exact saved-plan
  apply `43101777948` (deployment `7721332861`).
- The plan reported 0 additions, 6 in-place Lambda package updates, 0 destroys,
  0 drift, and 8 output changes. Migrations passed; all six Lambda functions
  are Active/Successful with `CodeSha256=vg52ZDcTSAhZ3hK7dra2Ou7oExSdzGDPjMBjoNQe4ZM=`;
  `/healthz` returned `{"status":"ok","product":"davdeploy"}`.
- All seven GitHub CI jobs passed for the release-evidence content at commit
  `86001cbdd7d065ed780ec3d43161fdaacbd36a99` in run
  [43103241448](https://github.com/Bepoadewale/davdeploy/actions/runs/43103241448).
- Nova plan runner, role verification, credential broker, Terraform state API,
  plan review, and hosted certification remain disabled. No Nova customer plan
  or workload was applied, operated, health-checked, or certified.
- PR #318 pricing work remains closed and held for account-owner direction.

## Research / references used

- Protected plan `43098415855`, exact saved-plan apply `43101777948`, and
  deployment `7721332861`.
- Read-only AWS identity and Lambda package/gate queries in account
  `654654474502`, region `us-east-1`, plus API health at
  `https://api.davdeploy.tech/healthz`.
- Historical release evidence `docs/test/test358.md`; current release evidence
  `docs/test/test359.md`.
- `docs/product/EXECUTION_READINESS_MATRIX.md`,
  `docs/IMPLEMENTATION_STATUS.md`, `PROJECT_STATUS.md`, and `CODEX_BACKLOG.md`.

## Work planned for the PR

- Record the exact PR #359 control-plane release and retain PR #358 as
  historical evidence.
- Keep the initial no-job plan failure and successful retry accurately
  distinguished.
- Reconcile source, deployment, feature gates, pricing and customer-lifecycle
  limitations in status and readiness documents.
- Retain all capability catalogue and implementation scope; do not imply that
  control-plane deployment certifies customer workloads.

## Acceptance criteria

- [x] Exact source commit, plan/apply run, deployment ID, action summary,
  migration, Lambda package, API health, account/region, and gate evidence is
  recorded.
- [x] PR #359's deployed source is distinguished from customer planning,
  approval, apply, health, recovery and teardown readiness.
- [x] Historical PR #358 release evidence remains intact.
- [x] Pricing is clearly unavailable and PR #318 remains held; the coverage
  matrix and capability counts are retained.
- [x] Documentation convention checks and `git diff --check` pass for the
  release-evidence content at `86001cb`.
- [x] All seven required hosted CI jobs passed for that content in run
  `43103241448`. This ticket evidence update must also pass the PR's required
  final-head checks before merge.
- [x] This documentation PR did not dispatch or perform an AWS mutation. The
  separate protected #359 release is recorded as evidence.

## Acceptance status

Release content and its hosted checks are complete. The ticket now records
those results; final-head checks for this ticket update remain required before
merge.

## Tests / validation performed

- `python scripts/check_doc_conventions.py` and `git diff --check` passed on
  the release-evidence content at `86001cb`.
- All seven required GitHub CI jobs passed in run `43103241448` for that
  release-evidence content. The final ticket-only update requires a fresh
  successful final-head check before merge.
- No customer workload test was run by this documentation PR; no new runtime
  test file is required for PR #360.

## Evidence files produced

- `docs/test/test359.md` — exact protected deployment evidence for PR #359.
- `docs/test/test358.md` — preserved prior deployment evidence for PR #358.

## Boundaries

This PR records technical evidence. It does not enable Nova planning or
execution, alter customer resources, or contain the private goal ledger,
pricing strategy, credentials, or operational access notes.

## Follow-up work

Keep final cost-bound approval blocked until trusted complete regional pricing
is available under the held account-owner pricing direction. Verify the
customer plan role and effective permissions, then enable and exercise hosted
planning only after tenant-isolated state and artifact protections are proven.
Apply, health, recovery, retained-data handling, teardown and the composed
scenario matrix remain unproved.
