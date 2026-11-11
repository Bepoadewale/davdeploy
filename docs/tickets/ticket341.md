# ticket341 — document Nova plan-role production release evidence

PR: [#341](https://github.com/Bepoadewale/davdeploy/pull/341) (draft)
Branch: `docs/record-nova-340-deployment-341`

## Problem / goal

Record the exact saved Terraform plan, protected production apply, post-release
checks, and remaining limitations for backend PR #340. Keep source-validation
evidence separate from production release evidence.

## Current repo state

- Backend `main` includes PR #340 at merge commit
  `8d3b4764bcefae8cb9f93a930b064e10fd893762`.
- Terraform plan run `42973143188` and apply run `42974086012` both completed
  successfully for that commit.
- The plan-runner, plan-review, customer-role-verification, and Terraform state
  API gates remain disabled. No customer role or workload was changed.

## Research / references used

- The recorded release artifacts are the exact versioned Terraform plan and
  immutable Lambda package created by the repository's
  `.github/workflows/terraform-plan.yml` workflow.
- Apply evidence is from `.github/workflows/terraform-apply.yml`, which checks
  the plan commit and manifest digest before applying the saved plan, then
  invokes the migration Lambda and requires an explicit completion result.
- Source implementation and local verification are documented in
  `docs/tickets/ticket340.md` and `docs/test/test340.md`.

## Work planned for the PR

- Record run IDs, commit, account, region, saved-plan digest, redacted action
  summary, apply result, Lambda status/code hash, API health, and feature-gate
  values in `docs/test/test341.md`.
- Reconcile PR #340's ticket and local-only test evidence with its merge and
  later production control-plane release.
- Preserve sensitive plan values, environment values, and customer details
  from the evidence.

## Acceptance criteria

- [x] Plan and apply run IDs and saved-plan digest are recorded.
- [x] Resource actions and drift are summarized without sensitive values.
- [x] Post-apply Lambda status, migration result, feature flags, and API health
  are recorded.
- [x] Customer roles/workloads and hosted Nova gates are clearly stated as
  unchanged/disabled.
- [x] Local documentation convention checks and `git diff --check` pass.
- [ ] Required final-head CI passes.

## Acceptance status

The release completed successfully with six in-place Lambda package updates,
zero creates/deletes, a successful migration check, all six functions active,
and API health returning `ok`. The final docs-only PR must pass convention
checks and CI before merge.

## Tests / validation performed

- Evidence was cross-checked against Terraform plan run `42973143188`, apply
  run `42974086012`, read-only AWS Lambda checks, and the public API health
  endpoint.
- `python3.12 scripts/check_doc_conventions.py` — passed after the final edits.
- `git diff --check` — passed.
- No runtime code or Terraform configuration is changed in this PR.

## Evidence files produced

- `docs/test/test341.md`
- Reconciled: `docs/test/test340.md`, `docs/tickets/ticket340.md`

## Boundaries

This PR records an already-completed authorized production release. It does
not change runtime code, customer permissions, infrastructure, plan/apply
gates, or product claims. It does not claim customer execution readiness.

## Follow-up work

Continue the disabled hosted plan request and approval path, finish regional
pricing integration when account-owner direction is available, and implement
separately verified apply, health, recovery, and teardown contracts before
enabling customer execution.
