# ticket380 — reconcile Nova network profile source status

PR: [#380](https://github.com/Bepoadewale/davdeploy/pull/380) (draft)
Branch: `docs/reconcile-nova-network-profile-380`

## Problem / goal

PR #379 merged a narrow, region-bounded metadata-read profile for proposed
VPCs, subnets, and security groups. Current readiness and project-status docs
still say those resource types are unsupported and describe an older backend
source as current. Reconcile source/deployment records without claiming that
the updated role template is deployed, that customer roles are effective, or
that hosted Nova planning is enabled.

## Current repo state

Backend `main` is `c3046f37f0d09fb0b1a26c26cab4be9ffe7d881c` after PR #379.
Merged-main CI run `43249113529` passed all seven jobs. The latest verified
hosted control-plane release remains PR #377 commit
`40439ab6b493a40c522102fa88de1c48043b4177`, deployed by exact saved-plan apply
`43192601048`. PR #379 is merged source only; its customer role template has
not been deployed or installed, and no customer role or workload was changed.

## Research / references used

- Backend PR #379 and its source/evidence: `docs/tickets/ticket379.md` and
  `docs/test/test379.md`.
- Backend execution matrix and status records listed in the implementation
  diff.

## Work planned for the PR

- Reconcile current-source records with PR #379 and merged-main CI evidence.
- Preserve the distinct deployed version and all unresolved role, pricing,
  state, approval, apply, health, recovery, and teardown gates.
- Add concise docs-only evidence and run documentation convention/diff checks.

## Acceptance criteria

- [x] Current source, deployed source, and hosted feature gates are accurately
      distinguished.
- [x] VPC/subnet/security-group plan metadata reads are described as merged
      source and not deployed/effective customer-role evidence.
- [x] All product claims and capability scope remain intact.
- [x] Documentation conventions and diff checks pass.
- [x] Final-head CI and manual review pass; no deployment or runtime evidence
      is claimed.

## Acceptance status

- [x] Documentation reconciliation, local validation, manual review, and PR CI
      complete; no deployment or runtime evidence is claimed.

## Tests / validation performed

- `python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- PR CI run `43251043501` passed all seven required jobs on head `fc99258`.
- Manual final-diff review confirmed the source/deployment distinction and
  that all product claims remain present.

## Evidence files produced

- `docs/tickets/ticket380.md`
- `docs/test/test380.md`

## Boundaries

This PR changes documentation only. It does not deploy code, change AWS roles,
enable hosted planning, call Nova, create a customer plan, or mutate AWS
resources. PR #102 remains draft. Pricing PR #318 remains closed/held; do not
reopen or replace it.

## Follow-up work

Continue dependency-ready plan-only execution, effective customer-role
verification, tenant-isolated state, complete regional pricing, exact-plan
approval, apply, operational health/recovery, teardown, and hosted scenario
certification. No Nova-generated customer workload has been applied,
operated, or certified.
