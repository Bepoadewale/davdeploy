# ticket403 — reconcile Nova plan-policy status after PRs #401 and #402

PR: https://github.com/Bepoadewale/davdeploy/pull/403 (draft)
Branch: `docs/nova-policy-matrix-status-403`

## Problem / goal

Update the technical status and capability evidence to reflect that PRs #401
and #402 are merged source. Preserve the limits of both policy checks and
continue to distinguish merged source from deployment and customer execution.

## Current repo state

Backend `main` is `653619d` after PR #402. PR #401/#402 modify deterministic
policy on actual Terraform plans; neither applies infrastructure nor proves
Nova-hosted customer execution. The control plane is deployed through PR #390.
Pricing remains held; exact-plan customer apply, health, recovery, and teardown
are not available.

## Research / references used

- [`EXECUTION_READINESS_MATRIX.md`](../product/EXECUTION_READINESS_MATRIX.md)
- [`NOVA_CAPABILITY_EVIDENCE_MATRIX.md`](../product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md)
- [`ticket401.md`](ticket401.md)
- [`ticket402.md`](ticket402.md)
- [`test401.md`](../test/test401.md)
- [`test402.md`](../test/test402.md)

## Work planned for the PR

- Replace draft-only wording with merged-source wording for the network ACL
  and EC2 metadata policy checks.
- Add their exact CI and test evidence without claiming AWS deployment or
  customer workload coverage.
- Preserve the network topology, EC2 default-override, and wider capability
  gaps.
- Reconcile ticket #402's PR state and keep pricing/apply/lifecycle blockers
  clear.

## Acceptance criteria

- [x] Both matrices identify #401/#402 as merged source and preserve limits.
- [x] Tickets #401/#402 identify their merged state and evidence.
- [x] No hosted or deployed customer capability is claimed.
- [x] Documentation conventions and diff checks pass.
- [x] Required GitHub checks passed all seven jobs in run
      [`43518623188`](https://github.com/Bepoadewale/davdeploy/actions/runs/43518623188)
      for implementation revision `b117109`.
- [x] Final evidence revision `87002c3` passed all seven jobs in run
      [`43519328914`](https://github.com/Bepoadewale/davdeploy/actions/runs/43519328914).
- [x] Final evidence revision `567c6fc` passed all seven jobs in run
      [`43520296502`](https://github.com/Bepoadewale/davdeploy/actions/runs/43520296502).
- [x] Final evidence revision `0a03fbb` passed all seven jobs in run
      [`43520799569`](https://github.com/Bepoadewale/davdeploy/actions/runs/43520799569).

## Acceptance status

Status and capability documents reflect the merged policy checks and their
limits. Local documentation conventions, diff checks, and all seven hosted CI
jobs pass on each revision, including final head `0a03fbb`. No source
capability is deployed by this documentation PR.

## Tests / validation performed

`GITHUB_PR_NUMBER=403 ... scripts/check_doc_conventions.py` and
`git diff --check` passed. GitHub Actions run `43518623188` passed all seven
jobs for `b117109`; evidence revisions `87002c3`, `567c6fc`, and final head
`0a03fbb` passed all seven jobs in runs `43519328914`, `43520296502`, and
`43520799569` respectively.

## Evidence files produced

`docs/test/test403.md`; documentation-only change, no runtime or cloud tests.

## Boundaries

This PR records source and test evidence only. It does not change policy code,
deploy the policy to AWS, enable apply, or claim customer workload readiness.

## Follow-up work

Continue the hosted plan, pricing, exact approval, apply, health, recovery,
teardown, and composed-scenario gates in the private goal ledger.
