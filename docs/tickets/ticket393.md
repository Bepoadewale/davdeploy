# ticket393 — bind proposal health and recovery requirements to saved plans

PR: https://github.com/Bepoadewale/davdeploy/pull/393
Branch: `feat/bind-proposal-verification-manifest-393`

## Problem / goal

The shared Nova proposal includes health assertions, recovery needs, cost
assumptions, assumptions, and limitations, but the persisted exact-plan
manifest currently omits them. Carry these typed proposal fields into the
manifest with a clear unexecuted/unverified status so plan review can inspect
what Nova proposed alongside the saved Terraform plan.

## Current repo state

Backend `main` is at `83eee489fd898b855445619eb0d6405f2ee34e7c` (PR #392).
The current manifest binds proposal digests, tenant state, policy and the
saved plan but does not expose the proposal's verification/recovery contract.
No hosted customer plan or health probe has run.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py`
- `apps/api/src/davdeploy/generated_plan_artifacts.py`
- `apps/api/src/davdeploy/nova_plan_codebuild.py`
- `apps/api/src/davdeploy/service.py`
- Tests for generated plan manifests and Nova plan persistence.

## Work planned for the PR

- Add a bounded, typed proposal-evidence section to the canonical manifest.
- Mark health assertions as proposed/not executed and recovery/cost assumptions
  as unverified; do not treat them as successful observations or pricing.
- Recompute and verify the exact manifest in both runner and control-plane
  result persistence, with a version increment.
- Add tests for content binding, bounds, status labels, and mismatch rejection.

## Acceptance criteria

- [ ] The manifest contains the exact validated health/recovery/cost-assumption
  contract associated with the proposal digest.
- [ ] The manifest clearly states that proposed health assertions were not
  executed and recovery/cost assumptions are unverified.
- [ ] Proposal evidence is bounded and malformed or digest-mismatched evidence
  fails closed during persistence.
- [ ] Existing tenant/state/policy/plan artifact bindings remain intact.
- [ ] Focused and full verification, docs conventions, and required CI pass.
- [x] No customer plan, apply, or AWS workload is executed by this PR.

## Acceptance status

- [x] The typed verification and recovery requirements are included in the exact-plan manifest.
- [x] The manifest labels the requirements as proposed and unexecuted; plan pricing remains unavailable.
- [x] Manifest construction checks proposal type, region, and canonical digest binding.
- [x] Focused and full verification passed locally; hosted CI is pending.
- [x] No customer plan, apply, or AWS workload was executed.

## Tests / validation performed

- Focused: `tests/test_generated_deployment_contract.py tests/test_generated_plan_artifacts.py tests/test_nova_plan_codebuild.py tests/test_nova_plan_runs.py` — 122 passed.
- `make verify` — 1,064 passed; Ruff, OpenAPI snapshot, Actions configuration, and Docker Compose configuration checks passed. One existing Starlette/httpx deprecation warning remains.
- Documentation convention check and `git diff --check` — passed.
- GitHub Actions, independent review, and merge remain pending.

## Evidence files produced

- `docs/tickets/ticket393.md`
- `docs/test/test393.md` (to be added).

## Boundaries

This PR records proposed verification requirements with a plan; it does not
claim or perform health checks, customer apply, recovery, pricing, or teardown.

## Follow-up work

Implement typed deterministic probes and persist their actual observations
after separately authorized customer apply. Integrate trusted pricing before
final cost-bound approval.
