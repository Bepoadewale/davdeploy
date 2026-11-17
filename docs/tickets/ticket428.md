# ticket428 — refresh Nova capability evidence status

PR: https://github.com/Bepoadewale/davdeploy/pull/428
Branch: `docs/nova-provenance-ledger-428`

## Problem / goal

The Nova capability evidence matrix predates merged PRs #425–#427 and does not
distinguish the latest source-level intent provenance from the deployed
control-plane version. Its PR #399 head and CI evidence are also stale. Refresh
the matrix so readers can see the current source/runtime boundary.

## Current repo state

Backend `main` is `bd6288b6147888d3e6aeee918012fc74cb8d233d`. It includes bounded
Nova schema repair, validated proposal digests, and versioned original-context
digests. Hosted runtime remains at PR #420 commit
`9951caa9244128b1551fea3af66b1bdbf884c800`. PR #399 remains open/draft at
`ac0d29d279ffb622a610c873c08a5dda9acd1c2d`, with all seven fresh-head checks
passing in run `44192118631`.

## Research / references used

- `DAVDEPLOY_NOVA_GOAL.md`, especially packages 1 and 3 and their gates.
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket425.md`, `ticket426.md`, `ticket427.md`
- `DAVDEPLOY_NOVA_GOAL_STATUS.md` (private local execution ledger)

## Work planned for the PR

- Refresh the matrix's source/runtime snapshot, PR #399 evidence, and hosted
  lifecycle boundary.
- Record the Nova intent schema-repair and provenance changes as source-level
  evidence, not deployed or customer-workload evidence.

## Acceptance criteria

- [x] Matrix names current backend source and separately deployed runtime.
- [x] Matrix records merged #425–#427 source evidence and current #399 head/run.
- [x] No hosted Nova workload or customer sign-up is inferred from source state.
- [x] Documentation conventions and diff checks pass.
- [x] All seven required GitHub checks pass on the matrix update commit
  `79406af` in run `44193547583`.

## Acceptance status

Implementation is complete and documentation checks pass. All seven required
checks passed on the matrix update commit `79406af` in run `44193547583`. This
evidence-only ticket update receives a fresh PR run before merge.

## Tests / validation performed

`GITHUB_PR_NUMBER=428 python3.12 scripts/check_doc_conventions.py` and
`git diff --check` pass. Final-head run `44193547583` passed all seven checks on
the matrix update commit `79406af`. The evidence-only ticket follow-up will be
covered by a fresh run; no customer workload evidence file is required because
no customer workload was run.

## Evidence files produced

- `docs/tickets/ticket428.md`
- Updated `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- No `docs/test/test428.md` is required for a documentation-only change.

## Boundaries

Documentation only. No AWS API operation, Terraform plan/apply, hosted runtime
change, credential issuance, user-attribute inspection, or customer workload is
included. The four Cognito identities checked during this session are not
customer-workload certification or a workspace count.

## Follow-up work

The customer-owned test target and hosted Nova plan/apply/health/recovery/
teardown/absence lifecycle remain outstanding. Keep PR #399 draft with its
apply and credential gates disabled.
