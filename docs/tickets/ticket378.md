# ticket378 — record the deployed Nova intent scope guard

PR: [#378](https://github.com/Bepoadewale/davdeploy/pull/378) (draft)
Branch: `docs/reconcile-nova-scope-guard-release-378`

## Problem / goal

Record the protected deployment and post-release evidence for PR #377's
out-of-scope Nova intent guard. Reconcile repository status documents with the
exact source, plan, apply, deployed package, health check, and disabled hosted
planning gates.

## Current repo state

- Backend `main` is PR #377 merge `40439ab6b493a40c522102fa88de1c48043b4177`.
- PR #377 is deployed by exact saved-plan apply `43192601048` as GitHub
  deployment `7733504560`; see `docs/test/test378.md`.
- The Nova plan runner, credential broker, plan reviews, Terraform state API,
  and hosted certification remain disabled.

## Work planned for the PR

- Update the release evidence and current source/deployed status in the
  execution matrix, implementation status, project status, backlog, and
  `docs/test/test378.md`.
- Preserve the limitation that no customer-authenticated intent journey or
  customer infrastructure workload was exercised by this release.
- Verify documentation conventions and diff formatting; pass all required CI.

## Research / references used

- Protected workflow evidence: Terraform plan run `43191437865`, apply run
  `43192601048`, and PR #377 source.
- AWS post-release observations: account `654654474502`, region `us-east-1`,
  six Lambda package states and `/healthz`.

## Acceptance criteria

- [x] Exact saved-plan deployment and post-release evidence are recorded.
- [x] Source/deployed status reflects PR #377 and keeps Nova planning gates accurately labelled.
- [x] No customer-authenticated intent journey or customer workload is claimed.
- [x] Documentation conventions and diff checks pass.
- [ ] Final-head CI and review pass.

## Acceptance status

- [x] Deployment evidence and status reconciliation are complete.
- [ ] Final-head CI remains.

## Tests / validation performed

- `python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Required GitHub CI — pending.

## Evidence files produced

- `docs/test/test378.md`
- `docs/tickets/ticket378.md`

## Boundaries

Documentation only. No runtime, AWS, customer-role, customer-plan, or
infrastructure changes are part of this PR.

## Follow-up work

Continue hosted Nova plan-only execution, pricing, approval, customer apply,
health, recovery, and teardown work; these are not complete because this PR
only reconciles the scope-guard control-plane release.
