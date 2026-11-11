# ticket335 — reconcile the November 10 backend release evidence

PR: [#335](https://github.com/Bepoadewale/davdeploy/pull/335)
Branch: `docs/record-backend-release-335`
Base: `main`

## Problem / goal

The backend plan-history APIs are deployed, but the implementation status and
Nova execution-readiness documents still describe the November 4 release as
current. Record the exact source and hosted release evidence without implying
that Nova customer planning, approval, apply, health, recovery, or teardown is
ready.

## Current repo state

- Backend `main` source `f0c6f3af36a0ab14a5dafb9a1684c41140da7eef` was
  deployed by protected Terraform apply run `42902934302` after plan run
  `42902031985`.
- PRs #333 and #334 provide tenant-scoped, exact-revision plan history. Their
  routes were included in the release, but authenticated customer access has
  not been exercised.
- Nova review, runner, role-verification, and state API feature switches are
  false. Customer plan/apply/lifecycle evidence is still absent.

## Research / references used

- Protected workflow runs `42902031985` (Terraform plan) and `42902934302`
  (Terraform apply).
- Backend PRs #333 and #334, their route contracts, and the read-only
  production observations recorded in `docs/test/test335.md`.
- `docs/IMPLEMENTATION_STATUS.md`,
  `docs/product/EXECUTION_READINESS_MATRIX.md`, and
  `docs/product/COMPOSED_EXECUTION_GOAL.md`.

## Work planned for the PR

- Record the exact deployed source/workflow evidence and feature-gate status.
- Clarify that HTTP 401 confirms route protection but not authenticated
  customer access.
- Preserve the older dated release details as historical evidence.

## Acceptance criteria

- [x] Record the exact plan/apply workflow IDs, source commit, plan summary,
      migration result, deployed Lambda identity, and read-only health/auth
      observations.
- [x] State which Nova feature switches remain disabled and whether hosted
      customer plan history has been authenticated end to end.
- [x] Reconcile stale “not deployed” statements for PRs #333/#334 without
      erasing historical evidence or overstating customer execution readiness.
- [x] Keep the private Nova goal ledger outside the repository.
- [ ] Run documentation conventions and diff checks; required GitHub checks
      pass.

## Boundaries

Documentation only. No customer workload execution, AWS resource mutation,
feature enablement, or public product claim change.

## Acceptance status

Documentation edits are complete. Convention and diff checks are being run;
GitHub checks remain the merge gate.

## Tests / validation performed

- Pending documentation convention and diff checks for this PR.
- No application tests or infrastructure operations are part of this
  documentation-only change.

## Evidence files produced

- `docs/test/test335.md`

## Follow-up work

Verify authenticated tenant-scoped plan history, then continue the gated
hosted planning and exact costed-approval work. This PR does not enable those
capabilities.
