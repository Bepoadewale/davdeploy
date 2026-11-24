# test485 — Isolated EC2 Auto Scaling lifecycle

Date: 2026-11-24

Execution type: Direct Terraform in the owner-controlled same-account customer
test boundary. This does not use Nova or the hosted control plane.

Repository: `Bepoadewale/davdeploy`.

Customer repository: None; direct same-account AWS service test.

Commit: In progress.

AWS account: `654654474502`.

AWS region: `us-east-1`.

Terraform root: `docs/test/fixtures/nova-asg-485` (local state; no backend).

Test ID: `nova-asg-485`.

## Intended test shape

- Dedicated VPC `10.248.0.0/16`, with two isolated `/24` subnets in separate
  available Availability Zones.
- No Internet Gateway, NAT Gateway, VPC endpoint, public IP, default route,
  ingress rule, or egress rule.
- One Auto Scaling group using the merged bounded module and generated-plan
  profile: Amazon Linux 2023 x86_64, `t3.micro`, IMDSv2 required, and a maximum
  of two instances.
- All managed resources tagged `TestId=nova-asg-485`.
- Local Terraform state only. No hosted API, worker, remote state, lock table,
  Nova dispatch, customer data, or application endpoint.

## Resources created

Pending. The reviewed creation plan contains nine resources: one VPC, two
subnets, one route table, two route-table associations, one security group,
one launch template, and one Auto Scaling group. It contains no destroy or
update actions. The plan specifies zero security-group ingress and egress
rules.

## Commands executed

- Verified AWS account `654654474502` and region `us-east-1`.
- Confirmed the exact `nova-asg-485` Auto Scaling group and EC2 instance
  inventory was empty before planning.
- Confirmed the Terraform run monitor had zero active operations.
- `terraform fmt -check -recursive docs/test/fixtures/nova-asg-485` passed.
- `terraform validate` passed for the local-state test root.
- Reviewed plan: nine creates, zero changes, zero destroys; zero security-group
  ingress and egress rules.
- Apply and lifecycle observations are pending.

## Observed result

Pending. No AWS resources have been created for this test as of ticket opening.

## Results

Pending. No AWS resources have been created for this test as of ticket opening.

Before each apply, record the reviewed plan summary and verify the caller,
monitor, and exact test-prefix inventory. Record each monitored run ID, root,
PID, and log path. Observe ASG and EC2 status at capacity one, scale to two,
then return to one. Do not print credentials or state contents.

## Teardown

Destroy the test stack through `scripts/terraform_run_monitor.py`. Retain the
local state file; do not commit it. Independently query the exact test tags and
resource names to verify absence. Record any AWS-managed retained metadata
separately from resources controlled by the Terraform stack.

## Final boundary

## Evidence boundary

The test can establish service lifecycle and EC2 system/instance status for
this exact shape. It does not establish guest application health, external
network access, AMI provenance, complete resource pricing, update/recovery
behavior, cross-account isolation, Nova authorization/dispatch, or a customer
deployment. The hosted control plane and its state/locks are untouched.
