# ticket487 — verify DynamoDB data recovery lifecycle

PR: [#487 — test: verify DynamoDB point-in-time recovery lifecycle](https://github.com/Bepoadewale/davdeploy/pull/487) (draft)
Branch: `test/dynamodb-recovery-lifecycle-487`

## Problem / goal

The bounded DynamoDB module requires on-demand billing, server-side encryption,
point-in-time recovery (PITR), and deletion protection. Existing evidence
verifies configuration but does not exercise this exact module root's data
read/write and point-in-time restore behavior. Add a small, disposable
same-account test using local Terraform state, without touching the hosted
control plane.

## Current repo state

- Backend `main` is `13e34c4c29d72b72cee3b553176e1b93059e3244` (PR #485).
- PR #473's source policy requires the bounded table profile and known,
  enabled PITR; the module also enables deletion protection.
- The capability matrix records prior DynamoDB PITR configuration evidence,
  but no application read/write or restore for this exact module root.
- PR #486 remains independent and open; this test starts from `main`.

## Research / references used

- [DynamoDB point-in-time recovery](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Point-in-time-recovery.html)
- [Restore a DynamoDB table](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/pointintimerecovery_restores.html)
- [RestoreTableToPointInTime API](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_RestoreTableToPointInTime.html)
- `infrastructure/terraform/modules/dynamodb-table/main.tf`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Work planned for the PR

1. Add a tagged Terraform fixture for exactly one `modules/dynamodb-table`
   instance, pinned to account `654654474502` and region `us-east-1` by
   explicit preflight.
2. Verify the live table is active, on-demand, encrypted, protected from
   deletion, and has PITR enabled.
3. Write a baseline item, restore to a recorded valid PITR timestamp, then
   write a later marker and prove the restored table includes the baseline
   but excludes the later marker.
4. Remove the unmanaged restored table, explicitly disable deletion
   protection on the exact disposable source table after test success, review
   the destroy plan, and destroy the source through the Terraform run monitor.
5. Record costs only as observed/verified; retain local state and keep Nova
   dispatch and hosted control-plane evidence separate.

## Acceptance criteria

- [ ] A fresh isolated local-state root uses the exact bounded DynamoDB
  module and only tagged resources in the verified test account/region.
- [ ] The live source table's billing, encryption, PITR, and deletion
  protection settings are independently observed.
- [ ] PITR restoration to a captured valid timestamp recovers a baseline item
  and omits a later synthetic write; restored table reaches `ACTIVE`.
- [ ] The restored table is deleted, source deletion protection is disabled
  on the exact disposable table only after the restore assertions pass, and
  monitored teardown removes the source.
- [ ] Independent AWS checks find no test tables; local Terraform state is
  empty and retained.
- [ ] Ticket, test evidence, and capability matrix distinguish direct
  customer-side data/recovery evidence from Nova dispatch or hosted execution.
- [ ] Required focused/full verification, Terraform format/validate,
  documentation checks, diff check, and all required CI checks pass before
  merge.
- [ ] No hosted control-plane resource, Terraform remote state, or customer
  workload changes.

## Acceptance status

The fixture and recovery harness are implemented. The reviewed create plan
contains exactly one tagged table; monitored apply
`nova-dynamodb-pitr-487-create-20261124` has started and its terminal result
is pending. No restore or item write has been attempted yet. The package is
direct same-account service evidence only; it does not claim Nova dispatch or
hosted execution.

## Tests / validation performed

The bootstrap documentation commit opened the draft PR before substantive
implementation. Five harness unit tests, Ruff, Terraform formatting and
validation, full local verification, documentation checks, and diff checks
pass. The live AWS lifecycle is in progress.

## Evidence files produced

- `docs/tickets/ticket487.md`
- `docs/test/test487.md`
- `docs/test/fixtures/nova-dynamodb-pitr-487/`
- `scripts/dynamodb_pitr_lifecycle.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Boundaries

Create only the explicitly tagged disposable table and its PITR-restored copy
in account `654654474502`, region `us-east-1`. Use local Terraform state and
the run monitor for every Terraform mutation. Do not touch the hosted control
plane, remote state, unrelated AWS resources, or protected local files. Keep
test item values synthetic and out of logs.

## Follow-up work

Keep full table cost, tenant-specific authorization, application-level
recovery, hosted Nova planning/apply, Nova dispatch, and cross-account behavior
as separate gates.
