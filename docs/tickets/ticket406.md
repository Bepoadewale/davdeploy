# ticket406 — reconcile Nova deployment readiness after PR #405

PR: https://github.com/Bepoadewale/davdeploy/pull/406
Branch: `docs/reconcile-nova-deployment-406`

## Problem / goal

Update the Nova readiness and capability records after deploying backend main
`74016e70aa7a702ebf3338cf1fbb43d4f563a838`. Distinguish deployed control-plane
policy and plan infrastructure from customer plan/apply/lifecycle evidence.

## Current repo state

Backend `main` is `74016e70aa7a702ebf3338cf1fbb43d4f563a838` (PR #405). The
exact saved-plan apply completed successfully, but repository readiness docs
still named PR #390 as the current hosted release and called PRs #401/#402/#404
source-only.

## Research / references used

- Terraform plan and apply workflow summaries for runs `43565505292` and
  `43566319945`.
- Read-only AWS Lambda, CodeBuild and runtime-flag queries after apply.
- API health check at `https://api.davdeploy.tech/healthz`.

## Work planned for the PR

- Record the protected plan/apply, migration, package and health evidence.
- Mark PRs #401/#402/#404 and the PR #303 correction as deployed where the
  current evidence supports it.
- Preserve limitations: no hosted customer plan, complete pricing, customer
  apply, workload health, recovery, teardown or absence verification.
- Keep the private Nova handoff ledger outside this repository.

## Acceptance criteria

- [x] Current source commit and deployed release are stated separately from
  customer workload readiness.
- [x] Plan and apply run IDs, reviewed action counts, migration outcome,
  Lambda package identity, runtime gates and `/healthz` are documented.
- [x] Capability matrix and backlog no longer label the deployed policy checks
  as source-only or runtime gates as disabled.
- [x] No customer workload or end-to-end capability is claimed from control-
  plane deployment evidence.

## Acceptance status

Documentation edits are complete; final PR CI remains the merge gate.

## Tests / validation performed

`python3 scripts/check_doc_conventions.py` and `git diff --check` passed for
this documentation-only change.

## Evidence files produced

See [`docs/test/test406.md`](../test/test406.md). This documentation PR adds no
runtime behavior.

## Boundaries

This PR records deployment evidence only. It does not enable another feature or
claim that customer infrastructure has been planned, applied, operated, or
destroyed.

## Follow-up work

Continue draft PR #399 apply/reconciliation implementation and resolve the
held pricing dependency only with account-owner direction.
