# ticket363 — require explicit DynamoDB recovery evidence in generated plans

PR: [#363](https://github.com/Bepoadewale/davdeploy/pull/363) (draft)
Branch: `security/dynamodb-pitr-plan-policy-363`

## Goal

Make actual Terraform plan review identify whether each generated DynamoDB table has point-in-time recovery (PITR), fail closed when its policy-critical PITR settings are unknown or malformed, and require PITR when the immutable proposal says backup is required. Keep Nova planning and execution feature gates disabled.

## Current state

Backend `main` is `36ec596f83cff1ed427fc04e79e1314ae30d6224` after PR #362. Actual-plan policy version `nova-generated-plan-2026-11-11.11` validates DynamoDB encryption and deletion protection, but does not currently validate the nested `point_in_time_recovery.enabled` or recovery period. AWS provider docs state PITR defaults to disabled when its block is omitted. The generated proposal has `recovery.backup_required`. Nova runner, state API, role verification, plan reviews and customer execution remain disabled.

## References

- AWS DynamoDB point-in-time recovery: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Point-in-time-recovery.html
- HashiCorp AWS provider `aws_dynamodb_table`: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/dynamodb_table.html
- Existing policy: `apps/api/src/davdeploy/generated_plan_policy.py`
- Existing focused tests: `tests/test_generated_plan_policy.py`

## Work planned

- Add critical unknown/malformed detection for DynamoDB PITR enabled and recovery-period values.
- Require enabled PITR for generated proposals whose recovery contract requires backups; otherwise surface a clear human-review finding when PITR is disabled or absent.
- Preserve explicit sensitivity/unknown handling and avoid exposing plan values.
- Add positive/negative regression cases for enabled, disabled, missing, unknown, malformed, and backup-required cases.
- Reconcile the implementation status after CI; do not deploy or enable hosted planning.

## Acceptance criteria

- [ ] Unknown or malformed PITR enablement/recovery-period metadata is denied before approval.
- [ ] A proposal with `recovery.backup_required=true` is denied unless PITR is known enabled with a valid 1–35 day recovery period.
- [ ] A proposal without required backups receives a human-review finding when PITR is disabled or omitted.
- [ ] A known enabled PITR setting with a valid period passes this specific policy check.
- [ ] Policy findings do not contain sensitive plan values.
- [ ] Focused tests, full `make verify`, docs conventions, diff check and required GitHub CI pass.
- [ ] Nova runner and customer execution remain disabled; no AWS workload is created or changed.

## Validation and evidence

- Pending implementation. Runtime evidence will be recorded in `docs/test/test363.md` because this changes executable plan policy.

## Boundaries and follow-up

- This does not implement pricing, approve plans, enable a hosted runner, apply resources, perform recovery, or certify customer workloads.
- DynamoDB restore behavior and actual application data-recovery verification remain future lifecycle acceptance work.
