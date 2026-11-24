# test487 — DynamoDB point-in-time recovery lifecycle

Date: 2026-11-24 (in progress)

Execution type: Direct same-account AWS test using local Terraform state.

Customer repository: None.

Commit: Bootstrap documentation only; implementation and test run pending.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The fixture creates one `modules/dynamodb-table` source table named
`davdeploy-nova-dynamodb-pitr-487-20261124a1b2`, tagged with
`TestId=nova-dynamodb-pitr-487-20261124a1b2`. It uses on-demand billing,
module defaults for encryption/PITR/deletion protection, and no indexes,
streams, replicas, or other AWS services. The AWS CLI profile and caller
account were verified before mutation. Terraform state remains local and will
be retained after teardown.

The PITR restore creates one second temporary DynamoDB table. Neither table
has indexes, streams, replicas, or other AWS services.

## Commands executed

1. Generate and review a Terraform plan that creates only the tagged source
   table; apply it through `scripts/terraform_run_monitor.py`.
2. Observe `ACTIVE`, `PAY_PER_REQUEST`, server-side encryption, deletion
   protection, and PITR `ENABLED` directly from DynamoDB APIs.
3. Write one synthetic baseline item. Wait until DynamoDB reports a
   `LatestRestorableDateTime` later than that write, restore to that captured
   timestamp, and then write a second item after the restore point.
4. Verify the restored table becomes `ACTIVE`, contains the baseline, and
   excludes the later item. Tag and delete the restored table; verify its
   absence.
5. After the restore assertions pass, disable deletion protection directly on
   the exact disposable source table and confirm the change. Review the source
   destroy plan, destroy through the run monitor, and independently verify the
   source table is absent and local state is empty.

AWS documents that a PITR restore creates a new table, the latest restorable
time typically lags current time by about five minutes, and tags, deletion
protection, and PITR settings must be configured separately on the restored
table. This procedure uses an explicit timestamp returned by DynamoDB rather
than assuming elapsed time is sufficient.

## Observed result

The saved create plan contained exactly one create, zero changes, and zero
deletes. It specified the exact table name/tag, `PAY_PER_REQUEST`, enabled
server-side encryption, enabled PITR, and enabled deletion protection. The
monitored create run `nova-dynamodb-pitr-487-create-20261124` started at
`2026-11-24T19:26:35Z`; its terminal result and Terraform PID are pending the
five-minute monitor interval. No item write or restore has run yet.

## Teardown

Pending. The restored table will be tagged and deleted by the evidence script.
After its recovery assertions pass, source-table deletion protection will be
disabled through one exact DynamoDB API call; the source destroy will run
through the Terraform monitor. Independent AWS absence checks and an empty
local state will be recorded.

## Final boundary

This test can establish the exact module's DynamoDB data read/write and
point-in-time recovery behavior plus teardown for this small table shape. It
does not establish Nova authorization, dispatch, credential issuance, hosted
execution, tenant-isolated state, full DynamoDB costs, application-level
recovery, or support for other table shapes. The hosted control plane remains
untouched.
