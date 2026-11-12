# ticket366

PR: #366
Branch: docs/reconcile-nova-secret-contract-366

# PR #366 — Reconcile Nova readiness after PR #365

## Problem / goal

Update the durable readiness and implementation status pages to include PR #365's typed secret-reference input validation while preserving the fact that customer secret resolution and Nova execution remain unavailable.

## Current repo state

- Backend `main` includes PR #365 at `def21021a44c5ec39ddafc295c4c8c6b5ee7b896`.
- PR #365 rejects common literal credential and secret values unless represented as a typed `secret_reference` resource reference.
- The change is source-level input validation only. It does not provide tenant-scoped secret lookup, runtime secret retrieval, or hosted customer planning/apply.
- Hosted Nova execution, customer role installation, regional pricing, health/recovery, and teardown remain incomplete.

## Research / references used

- `docs/tickets/ticket365.md`
- `docs/test/test365.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/PROJECT_STATUS.md`
- `CODEX_BACKLOG.md`

## Work planned for the PR

- Add PR #365 to the current-source readiness summary and security gap description.
- Preserve the latest deployed control-plane version and all disabled Nova gate statements.
- Keep pricing PR #318 marked held pending account-owner direction.
- Record that PR #365 is not hosted customer secret resolution evidence.

## Acceptance criteria

- [x] Readiness matrix includes #365 and accurately states its limits.
- [x] Implementation status identifies #365 as the latest source hardening while retaining current deployed version/evidence.
- [x] Project status/backlog point to the remaining controlled secret-resolution gap.
- [x] Documentation conventions and `git diff --check` pass.

## Acceptance status

- [x] Readiness matrix and implementation status updated with #365 source evidence and limitations.
- [x] Project status and backlog point to the remaining controlled secret-resolution gap.
- [x] Documentation conventions and `git diff --check` pass.

## Tests / validation performed

- `python scripts/check_doc_conventions.py` passed.
- `git diff --check` passed.
- No AWS calls, model calls, customer plans, applies, or infrastructure changes were performed.

## Evidence files produced

- `docs/tickets/ticket366.md`
- This PR's documentation diff; no runtime evidence file is required for this documentation-only change.

## Boundaries

This PR does not implement secret resolution, change feature gates, enable customer execution, alter pricing policy, or claim customer-workflow readiness.

## Follow-up work

A separate security-reviewed implementation is required for tenant-scoped secret references and runtime usage.
