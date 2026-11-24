# test491 — private S3 artifact module lifecycle

Date: 2026-11-24 (complete).

Execution type: Direct same-account AWS module test with local Terraform state.

Customer repository: None.

Commit: `9599badbed8fff5516d17b597e400b971e9fcd53`.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The fixture uses exactly one `modules/artifacts` bucket,
`davdeploy-nova-artifacts-491-20261124-a1b2c3`, with the dedicated PR #491
prefix and unique `TestId=nova-s3-artifacts-491-20261124-a1b2c3`. Terraform
created exactly five resources: the bucket, public-access block, ownership
controls, versioning configuration, and server-side encryption configuration.
Local Terraform state is retained. The lifecycle helper used only
`nova-s3-artifacts-491/20261124-a1b2c3/synthetic.txt`, wrote two synthetic text
versions, verified the current and prior versions, and cleaned only versions
and delete markers for that exact key after confirming the bucket's test tag.

No customer content, control-plane state, network, database, or other AWS
service is in scope.

## Commands executed

1. Verify account `654654474502`, the unique bucket absence, and zero active
   Terraform monitor operations.
2. Review a saved create plan with exactly five creates, zero changes, and zero
   deletes; apply it through the monitor. Run ID
   `nova-s3-artifacts-491-create-20261124-a1b2c3`, Terraform PID `54017`,
   supervisor PID `54016`, finished at `2026-11-24T21:42:45Z`.
3. Independently read the bucket's public-access, ownership, versioning,
   encryption, and tags. Run the helper to upload synthetic v1/v2 contents,
   read both versions, verify the latest version, and clean only its exact
   object key.
4. Review the destroy plan with zero adds, zero changes, and five deletes. The
   monitored apply of that saved destroy plan succeeded as
   `nova-s3-artifacts-491-destroy-20261124-a1b2c3` (Terraform PID `55883`,
   supervisor PID `55882`, finished at `2026-11-24T21:48:56Z`).
5. Independently verify the bucket is absent, state is retained, and the
   Terraform monitor has no active operations.

## Observed result

The helper verified all four public-access-block settings,
`BucketOwnerEnforced` ownership, enabled versioning, and default AES256
encryption. It wrote two distinct object versions, read the latest v2 and
prior v1 content, and removed exactly two versions. Its output contained
status and version metadata only, not object contents. An independent
read-only check confirmed the bucket settings and tags and found zero versions
or delete markers for the exact test key. Before destroy, local Terraform
state contained the data identity and five module resources; the monitor had
58 records and no active runs. The saved destroy plan contained zero adds,
zero changes, and five deletes for this fixture. Monitored run
`nova-s3-artifacts-491-destroy-20261124-a1b2c3` succeeded at
`2026-11-24T21:48:56Z`; its Terraform PID was `55883` and supervisor PID was
`55882`. The log is
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-s3-artifacts-491-destroy-20261124-a1b2c3.log`.
An independent S3 read in the verified account found the bucket absent. The
local Terraform state file remains retained at 576 bytes and lists no module
resources. The run monitor has 59 records and zero active operations.

## Teardown

The reviewed destroy plan contained only five deletes for the unique test
bucket and its module settings. The monitored apply succeeded and independent
AWS reads verified the bucket absent. The helper removed only object
versions/delete markers for its exact key. Local Terraform state and provider
artifacts remain retained. Create log:
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-s3-artifacts-491-create-20261124-a1b2c3.log`.

## Final boundary

This test can establish only the exact artifact-module bucket settings and the
synthetic object behavior verified in this run. It does not prove Nova
authorization/dispatch, cross-account isolation, complete S3 pricing, object
retention or access-policy behavior beyond the observed settings, or a composed
application. The hosted control plane is untouched.
