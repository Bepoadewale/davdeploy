# ticket474

PR: [#474 — docs: reconcile Nova status through PR #473](https://github.com/Bepoadewale/davdeploy/pull/474) (draft)
Branch: `docs/reconcile-dynamodb-473-474`

## Problem / goal

Reconcile the active Nova status, backlog, and evidence matrix with merged PR #473 so the next work package uses a current handoff.

## Current repo state

- Backend `main` includes PR #473 (`aa72c68`), which adds DynamoDB module deletion protection and generated-plan checks for table identity, on-demand billing, encryption, deletion protection, and point-in-time recovery.
- The capability matrix DynamoDB row was updated in PR #473, but the matrix snapshot metadata and broader status documents still cite earlier heads.
- No AWS resource or hosted control-plane change is needed for this documentation package.

## Research / references used

- PR #473 and its passing CI run 45284594649.
- `docs/tickets/ticket473.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `CODEX_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `PROJECT_STATUS.md`

## Work planned for the PR

1. Update current backend head, source-only policy status, and lifecycle limitations in the active Nova status documents.
2. Preserve the distinction between accepted direct customer-side lifecycle evidence for tested shapes and Nova-specific authorization/dispatch evidence.
3. Keep the hosted control plane and AWS inventory unchanged.

## Acceptance criteria

- [ ] Active status documents identify PR #473 and accurately describe its bounded policy scope.
- [ ] No Nova workload, complete pricing, or customer lifecycle is claimed from this source-only change.
- [ ] The direct same-account customer lifecycle acceptance remains stated for exact tested resource shapes.
- [ ] No AWS or hosted control-plane resources are changed.
- [ ] Documentation conventions and `git diff --check` pass.
- [ ] Final-head CI and review/merge state are tracked; merge only after required checks pass.

## Acceptance status

Documentation reconciliation is in progress.

## Tests / validation performed

- Pending.

## Evidence files produced

- `CODEX_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `PROJECT_STATUS.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket474.md`

## Boundaries

Documentation only. Do not modify hosted control-plane resources or customer AWS resources. Preserve the protected untracked `--only-show-errors`, `.venv-pr399/`, Batch test state, and generated provider lock files.

## Follow-up work

Continue with the next dependency-ready Nova safety and evidence package.
