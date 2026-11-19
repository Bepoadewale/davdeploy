# ticket439 — reconcile current Nova goal evidence

PR: https://github.com/Bepoadewale/davdeploy/pull/439
Branch: `docs/nova-goal-evidence-reconcile-20261119`

## Problem / goal

Refresh the canonical Nova goal handoff and capability ledger against the
November 19 source and evidence state. Record the goal owner's acceptance of
the isolated same-account ECS customer run as customer-side plan/apply/health/
teardown evidence under the control-plane isolation requirement. Preserve the
separate fact that Nova did not generate or dispatch that run. Keep the full
26 architecture-entry and 30 Terraform-root scope and all remaining gaps
visible.

## Current repo state

- Backend `main` is `ec937ed257eec5eb0a21f69519df337a90bd79c0`.
- PR #399 is open and draft at `086d3afe0504adde0384275a6a3c713e2a42a75a`;
  its required checks passed in run `44297591687`. Apply and credential gates
  remain disabled; this PR's Nova-specific execution path has not been run.
- PR #437 is open and draft at `a1cecca156d5baac124750f8dd3d2c6721758ac5`;
  all seven checks passed in run `44510517423`. Its direct AWS evidence records
  a saved plan, isolated same-account ECS Express create, live health, teardown,
  and independent absence. The user accepted it for the general goal's
  customer-side plan/apply/health/teardown gate. It does not prove Nova
  generation, authorization, dispatch, cross-account isolation, or
  update/recovery.
- PR #438 is open and draft at `3e205e11ace285788fe7abe8e1e71b81d3db8d82`;
  all seven checks passed in run `44510141524`. It contains source-only
  append-only template hosting and a lock-free protected-state plan with four
  address moves and zero resource changes.
- PR #413 is merged. The Terraform run monitor currently has zero records and
  zero active runs. This documentation PR makes no AWS or control-plane change.

## Research / references used

- `docs/product/COMPOSED_EXECUTION_GOAL.md` — Nova goal handoff.
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` — 26 architecture entries
  and 30 Terraform roots with per-entry acceptance evidence.
- `docs/test/test437.md`, `docs/tickets/ticket437.md`, and PR #437 — isolated
  customer-side ECS evidence and owner acceptance.
- PR #399 — exact-plan apply source status and security boundary.
- PR #438 and `docs/test/test438.md` — append-only template-host source and
  protected-state plan evidence.

## Work planned for the PR

1. Refresh the current source/PR/operations snapshot without rewriting dated
   historical evidence.
2. Record the accepted customer-side ECS evidence in the canonical Nova goal
   status, with direct-run provenance and its explicit limits.
3. Preserve all 26/30 coverage entries and distinguish the accepted pilot
   evidence from per-entry policy, pricing, Nova execution, update/recovery,
   and lifecycle requirements that remain open.
4. State that no customer workload was applied or certified by Nova and that
   this documentation update did not touch the control plane or AWS.

## Acceptance criteria

- [x] Canonical goal status identifies current `main`, open PRs, their exact
      heads and required CI evidence.
- [x] The isolated ECS run is accepted as general-goal customer-side
      plan/apply/health/teardown evidence, without calling it Nova-generated or
      cross-account proof.
- [x] The 26 architecture entries and 30 Terraform roots remain intact; their
      broader per-entry requirements are not marked complete by the ECS pilot.
- [x] Remaining Nova-specific source, pricing, policy, role, and capability
      gaps are stated accurately.
- [ ] Documentation conventions, diff checks, and required PR CI pass.
- [x] No runtime, Terraform state/lock, AWS resource, or feature gate changes.

## Acceptance status

The handoff and matrix now reflect current source and accepted customer-side
evidence without shrinking the 26/30 scope or attributing the direct run to
Nova. Local documentation checks passed; required CI on the final PR head is
pending. No AWS resource or hosted control-plane state was changed. See
`docs/test/test439.md`.

## Tests / validation performed

- `GITHUB_PR_NUMBER=439 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Matrix integrity check — 26 architecture rows and 30 Terraform-root rows.
- Required hosted CI is monitored on the PR's final head.

## Evidence files produced

- `docs/tickets/ticket439.md`
- `docs/test/test439.md`

## Boundaries

Do not change or deploy the hosted control plane, its state, locks, runtime,
queues, or feature gates. Do not claim Nova initiated the ECS test or that the
full 26/30 capability matrix is complete. Preserve the protected untracked
backend file `--only-show-errors` and `.venv-pr399/` in the user's main
checkout.

## Follow-up work

Continue the dependency-ordered Nova implementation and acceptance work while
keeping the full architecture and Terraform-root scope visible. Any future
hosted control-plane change remains outside this PR.
