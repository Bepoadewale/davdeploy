# ticket405 — reconcile merged PR #404 evidence

PR: https://github.com/Bepoadewale/davdeploy/pull/405
Branch: `docs/reconcile-nova-eks-policy-405`

## Problem / goal

Reconcile the current Nova status documents after PR #404 merged its bounded
EKS managed-node metadata policy. Distinguish merged source and CI evidence
from deployment and customer EKS plan evidence.

## Current repo state

Backend `main` is merge commit `5572fab546e777f4adc38cfad99ede9b0290e89a`
after PR #404. Merged-main CI run `43563520542` passed all seven jobs. The
latest hosted control-plane package remains PR #390; PR #404 is merged source
only and has not been deployed or exercised on a customer EKS plan.

## Research / references used

- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/tickets/ticket404.md`
- `docs/test/test404.md`

## Work planned for the PR

- Update the current backend source snapshot in the readiness and capability
  matrices.
- Record #404 as merged source in implementation status and its ticket/evidence.
- Preserve the distinction between source policy, deployment, and customer
  EKS plan/lifecycle proof.

## Acceptance criteria

- [ ] All current status documents identify backend `5572fab` and PR #404 as
  merged source.
- [ ] The bounded policy behavior and remaining EKS limitations are accurate.
- [ ] No deployment, customer EKS plan, or workload readiness is claimed.
- [ ] Documentation conventions, diff checks, and all required CI pass.

## Acceptance status

In progress.

## Tests / validation performed

Pending documentation convention, diff, and GitHub CI checks.

## Evidence files produced

- `docs/tickets/ticket405.md`
- `docs/test/test405.md`

## Boundaries

Documentation reconciliation only. No AWS calls, deployment, customer plan,
or infrastructure mutation.

## Follow-up work

Continue with a dependency-ready Nova implementation task. Trusted regional
pricing remains held and must not be reopened or replaced without user direction.
