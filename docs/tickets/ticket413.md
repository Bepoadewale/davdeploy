# ticket413 — reconcile Nova capability coverage ledger

PR: #413 https://github.com/Bepoadewale/davdeploy/pull/413
Branch: `docs/nova-coverage-ledger-413`

## Goal

Reconcile source and hosted-version evidence after PR #412, then make the finite
26 architecture-entry / 30 implementation-root matrix actionable under the
Nova-led deployment workflow. Map every entry to an existing certification
scenario or an explicitly named additional test, required plan controls,
observable application behavior, artifacts and cost evidence, and hosted proof
status. Preserve gaps and distinguish source, isolated AWS, and hosted customer
evidence.

## Current repository and deployment state

- Source `main` is `017e53e329ff7c9be41f7a30e3c6c3451b3e4387` (merged PR #412).
- Open draft PR #399 (`feat/nova-exact-plan-apply-399`) is a separate exact-plan
  apply boundary. Its latest head `1085da7faf67e10d70bfa7fa64abf1819e6ec6f9`
  has all seven CI checks passing; it remains draft, unwired, and apply is not
  enabled for Nova customer workloads.
- The latest hosted backend source is `a9c5ca127e8e93845b215c795dd6755e6683869f`
  (PR #411), applied by Terraform apply run `43685318088` after plan run
  `43664906950`. Apply and migration steps passed. All six backend Lambda
  packages reported the same code hash on 2026-11-15; public `/healthz` returned
  HTTP 200. PR #412 source is not deployed.
- No Nova customer plan or workload has been applied, observed, recovered, or
  destroyed. The coverage inventory is not a readiness or launch claim.

## Research and source references

- `apps/api/src/davdeploy/module_catalogue.py` — 26 architecture entries.
- `apps/api/src/davdeploy/module_renderers.py` and
  `apps/api/src/davdeploy/certification_factory.py` — renderer and scenario
  bindings, including unsupported and unassigned entries.
- `apps/api/src/davdeploy/generated_plan_policy.py` and
  `apps/api/src/davdeploy/generated_plan_pricing.py` — shared actual-plan
  controls and current bounded pricing evaluator.
- `docs/product/EXECUTION_READINESS_MATRIX.md` — 26/30 source inventory.
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` — existing evidence
  cross-reference, currently stale at PR #405 / 2026-11-14.
- `docs/test/test406.md` — hosted PR #405 evidence; PR #411 apply run
  `43685318088` and `/healthz` independently rechecked for this PR.

## Work

1. Update source and hosted release snapshots without rewriting dated evidence.
2. Cross-reference each of the 26 architecture entries and 30 Terraform roots
   to an exact scenario or a clearly named additional acceptance test.
3. State concrete required plan checks, application health/failure behavior,
   artifact/ownership evidence, cost inputs, hosted lifecycle evidence, and
   current support stage for every entry.
4. Keep non-hosted and missing evidence explicit; do not infer implementation
   binding from semantic resemblance or claim arbitrary AWS coverage.
5. Keep the separate strategy and operational access notes private and outside
   both repositories.

## Acceptance criteria

- [ ] Current source, open PR, operations, hosted source/version and health
      evidence are reconciled and linked.
- [ ] All 26 architecture entries and all 30 implementation entries remain
      present and have a scenario/additional-test mapping.
- [ ] Every entry names required plan policy, observable behavior, artifacts,
      cost evidence, and hosted evidence/status without treating unrelated test
      results or fixtures as hosted customer proof.
- [ ] Unassigned, unsupported, missing-renderer, unpriced, and unverified entries
      remain visible and unpromoted.
- [ ] Documentation conventions and diff checks pass; required hosted CI passes.
- [ ] No runtime behavior, deployment permission, or customer execution gate is
      changed by this documentation PR.

## Validation planned

- Run `.venv/bin/python scripts/check_doc_conventions.py` and `git diff --check`.
- Required GitHub CI is the merge gate.
- Reconciliation is read-only: `gh` PR/workflow/deployment queries, AWS
  `sts:GetCallerIdentity`, Lambda code identity, and HTTPS health only.
- No customer workload, resource mutation, test fixture, or teardown is part of
  this PR.

## Evidence files

- `docs/tickets/ticket413.md`
- `docs/test/test413.md`

## Boundaries and follow-up

This PR does not enable Nova or customer apply, deploy PR #412 pricing, claim
cost completeness, or certify any of the 26/30 entries. The next implementation
dependency remains deterministic plan-cost completion and a hosted customer
plan journey, followed by exact-plan apply/lifecycle evidence. Any source or
runtime status change requires a separate implementation PR and hosted proof.

## Status ledger

- Status: in progress.
- Source commit: `017e53e329ff7c9be41f7a30e3c6c3451b3e4387`.
- PR: #413 draft; implementation not started.
- Deployed version: backend `a9c5ca127e8e93845b215c795dd6755e6683869f` (PR #411),
  apply run `43685318088`; PR #412 is source-only.
- Current operation: update the coverage matrix and PR evidence.
- Next command: run documentation convention and diff checks, then push and
  watch PR checks.
- Blockers: none known.
