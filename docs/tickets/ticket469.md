# ticket469

PR: [#469 — docs: reconcile Nova evidence through PR 468](https://github.com/Bepoadewale/davdeploy/pull/469) (draft)

Branch: `docs/reconcile-acm-468-469`

## Problem / goal

PR #468 merged source-only ACM request checks, while the active Nova handoff,
backlog, and capability matrix still identify PR #466 as current `main`.
Advance those snapshots without overstating certificate ownership, DNS, or
issuance evidence.

## Current repo state

- Backend `main` is `d0614ac10059a1b34fc1b3f98cdd4cde032b7ece` (PR #468).
- PR #468 requires a known certificate domain, DNS validation, RSA_2048, and
  disabled export in source plan checks.
- No ACM certificate or DNS resource was changed. Domain ownership,
  publication, issuance, renewal, and production TLS remain open.
- The hosted control plane remains at its previous release and was not
  accessed or changed.
- The Terraform run monitor has 41 terminal records and no active runs.
- Preserve `--only-show-errors`, `.venv-pr399/`,
  `docs/test/fixtures/nova-batch-retry-458/terraform.tfstate`, and generated
  provider lock files.

## Research / references used

- [PR #468](https://github.com/Bepoadewale/davdeploy/pull/468)
- `docs/tickets/ticket468.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `CODEX_BACKLOG.md`

## Work planned for the PR

1. Advance active source snapshots to PR #468.
2. Record the ACM request plan checks and their ownership/issuance limits.
3. Keep hosted control-plane and customer-workload evidence unchanged.
4. Preserve historical release and test records.

## Acceptance criteria

- [x] Active handoff, backlog, and matrix identify backend `main` at PR #468.
- [x] ACM plan checks are described as source-only with domain ownership,
  DNS publication, issuance, renewal, and production TLS evidence open.
- [x] Hosted release identity and no-mutation boundary remain unchanged.
- [x] Monitor reports 41 terminal records and no active runs.
- [x] Protected and generated untracked files remain untouched.
- [x] Documentation conventions and `git diff --check` pass.
- [x] Final-head CI and review/merge state are tracked on PR #469; merge only
  after all required checks pass.

## Acceptance status

The active documentation snapshots and validation record are reconciled on
PR #469. GitHub review and merge state are tracked on the PR.

## Tests / validation performed

- `GITHUB_PR_NUMBER=469 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Final-head CI is tracked on PR #469.

## Evidence files produced

- `CODEX_BACKLOG.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket469.md`

## Boundaries

- Documentation only; do not request ACM certificates or modify DNS.
- Do not access or change hosted control-plane resources.
- Do not claim domain ownership, issuance, renewal, production TLS, complete
  pricing, Nova dispatch, or broad AWS support from PR #468's checks.
- Preserve all protected and generated untracked local files.

## Follow-up work

Continue to the next dependency-ready source-policy slice. Keep each workload
and lifecycle capability tied to its actual evidence rather than static plan
checks alone.
