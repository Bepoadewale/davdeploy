# ticket352 — Reconcile deployed Nova plan-role readiness status

PR: [#352](https://github.com/Bepoadewale/davdeploy/pull/352) (draft)
Branch: `docs/reconcile-nova-role-release-352`
Base: `main`

## Goal

Record the verified deployment of PR #351 and keep the readiness matrix
accurate about what remains disabled. The API field is a display eligibility
hint; it does not attest effective role permissions or enable plan execution.

## Current repository state

Backend `main` includes PR #351 at merge commit
`512c9a89c977a338a839f5496d8273380cd39eb8`. Protected Terraform plan run
`43054392241` and apply run `43056460175` used that exact commit. The apply
updated six Lambda packages in place, added/destroyed no infrastructure, and
completed database migration verification. Read-only checks then confirmed
all six functions active with successful updates, account `654654474502`, and
`https://api.davdeploy.tech/healthz` returning HTTP 200. Nova plan reviews,
plan-only runner, customer role verification, credential broker, and state API
remain disabled. No hosted customer plan or workload has run.

## References

- `docs/tickets/ticket351.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- Terraform workflow evidence: runs `43054392241` and `43056460175`

## Work planned

- Update the readiness matrix with the exact PR #351 merge and protected
  release evidence.
- Update implementation status to state the current API gate and explicitly
  retain the customer-role, pricing, approval, apply, health, recovery,
  teardown, and certification gaps.
- Preserve the preceding PR #348 deployment evidence as historical context.

## Acceptance criteria

- [ ] Docs distinguish merged/deployed source from disabled runtime features.
- [ ] Exact plan/apply run IDs, resource action counts, migration, Lambda
      status, account/region, API health, and feature-gate results are recorded.
- [ ] No customer plan, role installation, infrastructure workload, or
      launch-readiness completion is claimed.
- [ ] Documentation conventions and diff checks pass; all required CI passes.

## Validation

Not run yet; documentation updates are in progress.

## Evidence files

No `docs/test/test352.md` is required because this documentation-only PR does
not run a customer workload or change executable behavior. Exact release
evidence remains in the Terraform workflow and current AWS/API observations.

## Boundaries and follow-up

This PR does not enable any Nova feature flag, configure a customer role, or
claim that a customer plan is available. Follow-on work still requires a real
verified customer connection, safe hosted state/runner integration, complete
regional pricing and exact-plan approval, then separately proven apply,
health, recovery, teardown, and composed-workload certification. PR #318's
pricing implementation remains held for account-owner direction.
