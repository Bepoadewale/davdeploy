# test487 — DynamoDB point-in-time recovery lifecycle

Date: 2026-11-24 (complete)

Execution type: Direct same-account AWS test using local Terraform state.

Customer repository: None.

Commit: Implementation/test changes on PR #487; final evidence commit pending.

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

Each PITR restore creates one second temporary DynamoDB table. Neither table
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
   absence. The live runs verified source writes and restored-table reads;
   source-read assertions added afterward have unit coverage but were not
   rerun live.
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
server-side encryption, enabled PITR, and enabled deletion protection.
Monitored create `nova-dynamodb-pitr-487-create-20261124` succeeded at
`2026-11-24T19:26:50Z` (Terraform PID `9433`); log:
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-dynamodb-pitr-487-create-20261124.log`.

AWS described the source as `ACTIVE`, `PAY_PER_REQUEST`, encryption
`ENABLED`, deletion protection true, PITR `ENABLED` with a 35-day period, and
all three test tags present. In the first script attempt, the restored table
reached `ACTIVE` with on-demand billing and encryption. Strongly consistent
reads returned `baseline` for the baseline key and no value for the later
marker, proving the restore timestamp boundary. The first delete attempt hit
`ResourceInUseException` because tag updates were still in progress. The
restored table was tagged and removed after the harness added bounded retry.
The second run with fresh item keys completed under run ID `20261124c3d4`.
Its captured PITR timestamp was `2026-11-24T19:44:42Z`; the restored table
was `ACTIVE` and encrypted, contained the baseline, and omitted the later
marker. The cleanup retry removed it, and the harness's absence waiter
completed successfully.

## Teardown

The restored-table cleanup waiter succeeded after retrying the AWS tag-update
race. An independent table-list check found only the tagged source table.
After the second recovery run passed, deletion protection was disabled on
that exact source table. The reviewed destroy plan contains zero adds, zero
changes, and one deletion of
`module.dynamodb_table.aws_dynamodb_table.this`. Monitored run
`nova-dynamodb-pitr-487-destroy-20261124` started at
`2026-11-24T19:54:05Z`, succeeded at `2026-11-24T19:54:16Z`, and used
Terraform PID `19380`. Its log is
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-dynamodb-pitr-487-destroy-20261124.log`.
Afterward, AWS `ListTables` filtered by the unique test prefix returned no
tables, `terraform state list` returned empty, and the local state file was
retained. The Terraform run monitor had zero active operations.

## Final boundary

This test establishes the exact module's source write, point-in-time recovery,
restored-table read behavior, and teardown for this small table shape. It
does not establish Nova authorization, dispatch, credential issuance, hosted
execution, tenant-isolated state, full DynamoDB costs, application-level
recovery, or support for other table shapes. The hosted control plane remains
untouched.
