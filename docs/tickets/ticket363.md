# ticket363 — require explicit DynamoDB recovery evidence in generated plans

PR: [#363](https://github.com/Bepoadewale/davdeploy/pull/363) (draft)
Branch: `security/dynamodb-pitr-plan-policy-363`

## Problem / goal

Make actual Terraform plan review identify whether each generated DynamoDB table has point-in-time recovery (PITR), fail closed when its policy-critical PITR settings are unknown or malformed, and require PITR when the immutable proposal says backup is required. Keep Nova planning and execution feature gates disabled.

## Current repo state

Backend `main` is `36ec596f83cff1ed427fc04e79e1314ae30d6224` after PR #362. Actual-plan policy version `nova-generated-plan-2026-11-11.11` validates DynamoDB encryption and deletion protection, but does not currently validate the nested `point_in_time_recovery.enabled` or recovery period. AWS provider docs state PITR defaults to disabled when its block is omitted. The generated proposal has `recovery.backup_required`. Nova runner, state API, role verification, plan reviews and customer execution remain disabled.

## Research / references used

- AWS DynamoDB point-in-time recovery: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Point-in-time-recovery.html
- HashiCorp AWS provider `aws_dynamodb_table`: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/dynamodb_table.html
- Existing policy: `apps/api/src/davdeploy/generated_plan_policy.py`
- Existing focused tests: `tests/test_generated_plan_policy.py`

## Work planned for the PR

- Add critical unknown/malformed detection for DynamoDB PITR enabled and recovery-period values.
- Require enabled PITR for generated proposals whose recovery contract requires backups; otherwise surface a clear human-review finding when PITR is disabled or absent.
- Preserve explicit sensitivity/unknown handling and avoid exposing plan values.
- Add positive/negative regression cases for enabled, disabled, missing, unknown, malformed, and backup-required cases.
- Reconcile the implementation status after CI; do not deploy or enable hosted planning.

## Acceptance criteria

- [x] Unknown or malformed PITR enablement/recovery-period metadata is denied before approval.
- [x] A proposal with `recovery.backup_required=true` is denied unless PITR is known enabled with a valid 1–35 day recovery period.
- [x] A proposal without required backups receives a human-review finding when PITR is disabled or omitted.
- [x] A known enabled PITR setting with a valid period passes this specific policy check.
- [x] Policy findings do not contain sensitive plan values.
- [ ] Required GitHub CI and review pass.
- [x] Nova runner and customer execution remain disabled; no AWS workload is created or changed.

## Acceptance status

- [x] Unknown or malformed PITR enablement/recovery-period metadata is denied before approval.
- [x] A proposal with `recovery.backup_required=true` is denied unless PITR is known enabled with a valid 1–35 day recovery period.
- [x] A proposal without required backups receives a human-review finding when PITR is disabled or omitted.
- [x] A known enabled PITR setting with a valid period passes this specific policy check.
- [x] Policy findings do not contain sensitive plan values.
- [x] Focused tests, full `make verify`, clean-room local proof, docs conventions and diff check pass. Required GitHub CI is pending.
- [x] Nova runner and customer execution remain disabled; no AWS workload is created or changed.

## Tests / validation performed

- Focused suite: `.venv/bin/python -m pytest -q tests/test_generated_plan_policy.py` — 143 passed.
- Full `make verify` — 998 tests passed; Ruff, Actions configuration, OpenAPI snapshot and Compose configuration passed. Existing Starlette/httpx deprecation warning remains.
- Isolated clean-room `make local-proof` passed 998 tests plus API/CORS contract, customer-plan E2E, fixture seed and trace checks. Six local demo/failure cases passed after one immediate post-restart attempt was retried after readiness succeeded. See `docs/test/test363.md`.

## Evidence files produced

- `docs/test/test363.md` — local clean-room and policy evidence; no AWS workload was run.

## Boundaries

- This does not implement pricing, approve plans, enable a hosted runner, apply resources, perform recovery, or certify customer workloads.
- DynamoDB restore behavior and actual application data-recovery verification remain future lifecycle acceptance work.

## Follow-up work

- Required GitHub CI and review remain before merge. Pricing, hosted planning, exact-plan approval/apply, health, restore, teardown, and composed workload certification remain separately incomplete.
