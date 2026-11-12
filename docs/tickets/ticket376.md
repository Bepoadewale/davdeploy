# ticket376 — reconcile and record the latest Nova control-plane release

PR: [#376](https://github.com/Bepoadewale/davdeploy/pull/376) (draft)
Branch: `docs/reconcile-nova-hosted-release-376`

## Problem / goal

The latest source/deployment status still reflected the release before PR #371,
#372, and #374. Record the exact #375-source deployment and keep the hosted
Nova readiness claims bounded to verified evidence.

## Current repo state

- Backend `main`: `7722ea339fd03dd6c137d28b5702b67bc5c42671` (PR #375 merge).
- Merged-main CI run `43164941399`: all seven required jobs passed.
- Protected plan `43166003130`; exact saved-plan apply `43167867502`;
  deployment `7730096971`.
- All six control-plane Lambdas are Active/Successful; API `/healthz` is HTTP
  200. No Nova customer workload was used.

## Research / references used

- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `PROJECT_STATUS.md`
- `docs/test/test369.md` and the protected plan/apply results for #375 source.
- The current Terraform plan summary and read-only AWS post-release checks.

## Work planned for the PR

- Reconcile current source/deployed release sections in the execution matrix,
  implementation status, and project status.
- Record plan counts, drift classification, immutable manifest digest,
  migration result, Lambda package identity, health result, and disabled gates.
- Preserve all incomplete customer planning, pricing, approval, apply,
  operation, recovery, teardown, and certification claims.

## Acceptance criteria

- [x] Source commit and merged-main CI are exact.
- [x] Plan/apply and post-release evidence are documented in `docs/test/test376.md`.
- [x] Drift is described as observed, expected verification policy; planned IAM
  role and policy resources were no-ops.
- [x] Customer planning and lifecycle remain explicitly unproven.
- [x] Documentation conventions and diff checks pass.
- [ ] Manual final-diff review completed.
- [ ] Final-head CI passes all required jobs.
- [ ] Required checks reviewed and PR merged.

## Acceptance status

- [x] Release evidence and source/deployment status are reconciled locally.
- [ ] Final PR review, CI, and merge remain outstanding.

## Tests / validation performed

`python scripts/check_doc_conventions.py` and `git diff --check` passed.
Runtime release evidence is recorded in `docs/test/test376.md`.

## Evidence files produced

- `docs/tickets/ticket376.md`
- `docs/test/test376.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `PROJECT_STATUS.md`

## Boundaries

This PR documents an already-completed protected control-plane release. It
makes no runtime, AWS, customer-role, customer-plan, or infrastructure changes.
The private Nova goal ledger remains outside the repository.

## Follow-up work

Continue with the next dependency-ready hosted plan/state, effective customer
role, pricing, exact-cost approval, and customer lifecycle integration work.
Do not claim the Nova hosted customer workflow is complete.
