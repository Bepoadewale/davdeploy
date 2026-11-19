# ticket442 — reconcile Nova handoff after SQS policy merge

PR: https://github.com/Bepoadewale/davdeploy/pull/442
Branch: `docs/nova-goal-status-after-sqs-441`

## Problem / goal

The canonical Nova goal handoff and capability matrix predate PR #441 and
still identify PR #399 as the current source head. Refresh current source, CI,
hosted-release, and execution status while retaining the full 26-architecture
and 30-root scope and the accepted customer-side ECS evidence.

## Current repo state

- Backend `main` is `48911bfb74fafc626076d216f6ed78a21f3be4ee` through PR #441.
- No PRs were open when this documentation update began.
- PR #441 merged with all seven required checks passing in run `44608565238`.
  Its SQS encryption plan rule is source-only and not deployed to the hosted
  control plane.
- The last recorded hosted control-plane release remains PR #420, applied in
  run `43982396577` after plan `43981566184`.
- PR #437's isolated ECS lifecycle is accepted for the general customer-side
  plan/apply/health/update/recovery/teardown evidence gate. Its run was direct
  Terraform, not Nova-generated or Nova-dispatched.
- PR #399 remains default-off at runtime; no Nova apply build, platform
  credential issuance, or Nova-originated customer workload is claimed.
- The Terraform run monitor has terminal history and no active run. Preserve
  the protected untracked `--only-show-errors` file and `.venv-pr399/`.

## Research / references used

- `docs/product/COMPOSED_EXECUTION_GOAL.md` — current Nova goal handoff.
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` — 26 architecture entries
  and 30 Terraform roots.
- `docs/tickets/ticket441.md` and `docs/test/test441.md` — SQS policy source,
  regression, and CI evidence.
- `docs/tickets/ticket440.md` and `docs/test/test440.md` — current direct ECS
  acceptance and isolated customer-role test evidence.
- Current GitHub PR, CI, and Terraform monitor state.

## Work planned for the PR

1. Refresh current source, PR, policy, and hosted-release facts.
2. State that PR #441 changes source policy only and leaves the hosted runtime
   and feature gates unchanged.
3. Preserve the owner-accepted customer-side ECS lifecycle evidence without
   claiming Nova-originated execution.
4. Keep the 26/30 scope and all remaining cost, policy, role, and lifecycle
   gaps visible.

## Acceptance criteria

- [x] Current backend source, PR #441 merge, and seven-check CI evidence are
      accurately recorded.
- [x] The source-only SQS rule is not described as deployed.
- [x] The accepted direct ECS test is counted for the general customer-side
      lifecycle gate and attributed to direct Terraform.
- [x] The 26 architecture entries and 30 Terraform roots remain intact.
- [x] Documentation conventions, diff checks, 26/30 matrix counts, and PR CI
      pass.
- [x] No hosted control-plane, AWS, Terraform state/lock, runtime, or gate
      mutation.

## Acceptance status

The canonical handoff and matrix now identify PR #441's merged source and
preserve the remaining goal scope. Documentation conventions and diff checks
pass, the matrix retains 26/30 entries, and all seven checks passed in run
`44610232683`. No AWS or hosted control-plane mutation is part of this PR.

## Tests / validation performed

- `GITHUB_PR_NUMBER=442 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Matrix count validation — 26 architecture entries and 30 Terraform roots.
- GitHub Actions run `44610232683` — all seven required checks passed.
- Current GitHub PR and required-check state verified for PR #441.
- Terraform run monitor inspected; no active run was reported.

## Evidence files produced

- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket442.md`
- `docs/test/test442.md`

## Boundaries

Do not modify the hosted control plane, its state, locks, runtime, queues, or
feature gates. Do not claim the SQS policy is deployed or that PR #437 was
Nova-generated. Do not mark the full matrix or Nova goal complete. Preserve the
protected untracked `--only-show-errors` and `.venv-pr399/` in the main
checkout.

## Follow-up work

Continue dependency-ordered implementation against the remaining policy,
pricing, dedicated-role, authorization/dispatch, and per-entry lifecycle gaps.
