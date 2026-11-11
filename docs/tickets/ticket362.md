# ticket362 — reconcile deployed RDS policy evidence

PR: [#362](https://github.com/Bepoadewale/davdeploy/pull/362) (draft; number reserved)
Branch: `docs/reconcile-rds-policy-release-362`
Base: `main`

## Problem / goal

Update the current project status, implementation status, execution readiness
matrix, and backlog to include the merged and deployed RDS backup-retention and
final-snapshot policy from PR #361. Keep historical records, execution gates,
and customer-readiness limits accurate.

## Current repo state

- Backend `main` and the protected control-plane release are at PR #361 merge
  commit `5775d766584f31f8a31b6b22e8e523b4e8a3f257`.
- Protected Terraform plan `43111051028` and exact saved-plan apply `43112125588`
  completed; GitHub deployment `7722764924`.
- The plan updated six existing Lambda packages in place, with no creates or
  destroys. Database migrations completed successfully, all six Lambdas are
  Active/Successful, and `/healthz` is healthy.
- PR #361 adds fail-closed RDS backup-retention checks and explicit final
  snapshot review. It does not enable hosted Nova planning or customer apply.
- The current status and readiness documents identify PR #359 as the latest
  hosted release and omit #361's RDS policy.

## Research / references used

- `docs/test/test361.md` — PR #361 policy implementation and deployment evidence.
- `docs/tickets/ticket361.md` — RDS policy scope and acceptance record.
- `docs/product/EXECUTION_READINESS_MATRIX.md` — current release and execution
  capability snapshot.
- `docs/IMPLEMENTATION_STATUS.md`, `PROJECT_STATUS.md`, and `CODEX_BACKLOG.md`.

## Work planned for the PR

- Add a current hosted-release entry with exact PR, merge commit, plan, apply,
  deployment, migration, Lambda and API-health evidence.
- Mark the RDS retention/snapshot policy as deployed while retaining the
  disabled Nova gates and remaining customer-workflow gaps.
- Preserve existing historical release evidence and capability matrix scope.

## Acceptance criteria

- [ ] Current release records cite the exact #361 commit, plan, apply and
  deployment evidence.
- [ ] The deployed policy behavior and its scope are described accurately.
- [ ] Nova plan, review, role verification, state, hosted certification and
  customer apply remain explicitly disabled or unavailable.
- [ ] Historical evidence and all architecture/implementation matrix entries
  are preserved.
- [ ] Documentation conventions and `git diff --check` pass.
- [ ] Required final-head CI passes before merge.
- [ ] No runtime or infrastructure changes are made by this PR.

## Acceptance status

Documentation updates are implemented and locally verified. Current-head CI
remains a merge gate. No Terraform deployment is required for this PR.

## Tests / validation performed

- `python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Final-head GitHub CI is required before merge.

## Evidence files produced

No new runtime evidence file is required; the source release evidence is
`docs/test/test361.md`.

## Boundaries

This PR changes documentation only. It does not enable feature flags, run a
customer plan, change AWS resources, reopen held pricing work, or claim the
Nova customer deployment workflow is ready.

## Follow-up work

Continue customer plan-role effective-permission verification, isolated hosted
plan execution and state, complete trusted pricing, exact plan approval/apply,
health and recovery, data retention, destroy verification, and composed
customer-workload certification.
