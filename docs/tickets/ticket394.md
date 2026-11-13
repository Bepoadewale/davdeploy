# ticket394 — reconcile source and deployment status after PR #393

PR: Pending creation
Branch: `docs/reconcile-plan-manifest-status-394`

## Problem / goal

Reconcile the current source and hosted-release status after PR #393. Make clear
that proposal health, recovery, cost assumptions and limitations are now bound
to the saved-plan manifest in source, but remain proposed/unvalidated and are
not evidence of pricing, probe execution, or a deployed customer workflow.

## Acceptance criteria

- [ ] Current source and merged-main CI identify PR #393 and its exact commit.
- [ ] Latest hosted control-plane deployment remains identified separately as PR #390.
- [ ] Product readiness and pricing/apply/health/lifecycle limitations remain accurate.
- [ ] Documentation convention and diff checks pass; required CI passes.
- [ ] No customer plan or workload is executed by this documentation change.

## Validation

Pending.
