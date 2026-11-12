# ticket373 — reconcile Nova RDS plan-access status

PR: [#373](https://github.com/Bepoadewale/davdeploy/pull/373) (draft)  
Branch: `docs/reconcile-nova-rds-access-373`

## Problem / goal

Reconcile the product readiness matrix, implementation status and backlog with
the merged source changes in PRs #371 and #372. State plainly that their RDS
metadata-read additions are merged source but not deployed, and do not enable
the hosted plan runner or claim customer planning. Preserve the full capability
scope and all existing customer-facing product claims.

## Current repo state

- Backend `main` is merge commit `c4d8bba4e7d328481293ec222ae26123b8843457`.
- PR #372 adds only exact RDS subnet-group metadata access; PR #371 adds exact
  DB/cluster metadata access. Neither has been deployed.
- Merged-main CI run `43156487303` passed all seven required jobs.
- The latest hosted release is still backend commit
  `0481696d8a9aa1c73d789b2076a23f9c07ccc1fb` with trust/account verification
  enabled by the later protected rollout. Runner, broker, state API, plan
  review and hosted certification remain disabled.
- No customer plan role is installed or verified. Pricing remains unavailable;
  PR #318 remains held. No Nova customer plan or workload has been applied,
  operated, health-checked, recovered, or destroyed.

## Research / references used

- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `CODEX_BACKLOG.md`
- PR #371 and PR #372 source, tickets and evidence files.

## Work to be done

- Update the current-source snapshot with backend `main` at `c4d8bba` and
  merged-main CI `43156487303`.
- Change PR #372 from draft to merged source, not deployed; preserve the exact
  RDS subnet-group action/resource scope and its limitations.
- Keep hosted-release state separate from source state and preserve the
  disabled runner, broker, state API and plan-review gates.
- Keep VPC/subnet/security-group reads, customer-role permission verification,
  pricing, approval/apply and customer workload evidence explicitly incomplete.

## Acceptance criteria

- [ ] Current source and merged-main CI evidence are exact and verified.
- [ ] PR #371/#372 are described as merged source, not deployed.
- [ ] No customer role, plan, approval, apply, health or teardown is claimed.
- [ ] Existing catalogue counts, product claims and scope are preserved.
- [ ] Documentation conventions and diff checks pass.
- [ ] Current-head review and required final-head CI pass.

## Validation

Documentation conventions, diff checks and final-head GitHub CI will be
recorded after the documentation update. This documentation-only PR makes no
AWS changes and requires no runtime-workload proof.

## Boundaries and follow-up

This PR changes documentation only. It does not enable the plan runner, install
a customer role, attest effective customer permissions, resolve regional
pricing, authorize an apply, or certify a workload. Continue with the next
dependency-ready security and hosted-execution work after reconciliation.
