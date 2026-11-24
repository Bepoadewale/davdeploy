# test491 — private S3 artifact module lifecycle

Date: 2026-11-24 (in progress).

Execution type: Direct same-account AWS module test with local Terraform state.

Customer repository: None.

Commit: PR #491 implementation/evidence commit pending.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The planned fixture uses exactly one `modules/artifacts` bucket with the
dedicated PR #491 prefix and a unique `TestId`. Expected Terraform resources
are the bucket, public-access block, ownership controls, versioning
configuration, and server-side encryption configuration. Local Terraform
state is retained. The lifecycle helper uses only one synthetic text object
key, writes two versions, verifies the current and prior versions, and cleans
only versions/delete markers for that exact key after confirming the bucket's
test tag.

No customer content, control-plane state, network, database, or other AWS
service is in scope.

## Commands executed

Pending reviewed AWS run. The intended sequence is:

1. Verify the AWS account, unique bucket absence, and zero active Terraform
   monitor operations.
2. Review a plan containing exactly the tagged `modules/artifacts` resources
   and apply through `scripts/terraform_run_monitor.py`.
3. Read back public-access, ownership, versioning, encryption, and tags through
   S3 APIs. Run the helper to upload synthetic v1/v2 contents, read both
   versions, verify the latest version, and clean only its exact object key.
4. Review the destroy plan, destroy through the run monitor, and independently
   verify that the bucket is absent while retaining local state and artifacts.

## Observed result

Pending AWS execution and independent verification.

## Teardown

Pending reviewed monitored destroy. Only the unique test bucket is in the
Terraform plan. The helper removes only object versions/delete markers for its
exact key, and local Terraform state/provider artifacts will be retained.

## Final boundary

This test can establish only the exact artifact-module bucket settings and the
synthetic object behavior verified in this run. It does not prove Nova
authorization/dispatch, cross-account isolation, complete S3 pricing, object
retention or access-policy behavior beyond the observed settings, or a composed
application. The hosted control plane is untouched.
