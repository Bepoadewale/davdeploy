# test486 — Encrypted Auto Scaling root volume

Date: 2026-11-24

Execution type: Direct Terraform in the owner-controlled same-account customer
test boundary. This does not use Nova or the hosted control plane.

Repository: `Bepoadewale/davdeploy`.

Customer repository: None; direct same-account AWS service test.

Commit: Implementation is in progress on PR #486; final evidence commit pending.

AWS account: `654654474502`.

AWS region: `us-east-1`.

Terraform root: `docs/test/fixtures/nova-asg-486` (local state; no backend).

Test ID: `nova-asg-486`.

## Intended test shape

- Dedicated VPC `10.247.0.0/16`, with two isolated `/24` subnets in separate
  available Availability Zones.
- No Internet Gateway, NAT Gateway, VPC endpoint, public IP, default route,
  ingress rule, or egress rule.
- One `t3.micro` Amazon Linux 2023 Auto Scaling instance with IMDSv2 required.
- One `/dev/xvda` root EBS mapping, 8 GiB gp3, encrypted, and deleted with the
  instance.
- Tag-capable managed resources use `TestId=nova-asg-486`.
- Local Terraform state only. No hosted API, worker, remote state, lock table,
  Nova dispatch, customer data, or application endpoint.

## Resources created

Pending. The reviewed plan is expected to create one VPC, two subnets, one
route table, two route-table associations, one security group, one launch
template, and one Auto Scaling group.

## Commands executed

- Verified AWS caller account `654654474502` with profile
  `ai-platform-pilot-key`; verified the test ASG and `TestId=nova-asg-486`
  instance inventory were empty.
- Verified the proposed `10.247.0.0/16` CIDR does not overlap the existing
  account VPCs `10.44.0.0/20` and `172.31.0.0/16`.
- Verified the Terraform run monitor had zero active operations before apply.
- `terraform -chdir=docs/test/fixtures/nova-asg-486 fmt -check -recursive`:
  passed; `terraform -chdir=docs/test/fixtures/nova-asg-486 validate`:
  passed.
- Reviewed the saved plan: nine creates, zero updates or deletes. The launch
  template sets one `/dev/xvda` root mapping to encrypted, delete-on-termination,
  gp3, 8 GiB.
- First monitored apply attempt `nova-asg-486-create-20261124` failed before
  AWS changes because no AWS profile was inherited. The monitored log records
  `No valid credential sources found`.
- The credentialed retry `nova-asg-486-create-keyprofile-20261124` failed
  before AWS changes because the saved plan was stale after local state
  metadata had been initialized.
- Refreshed and reviewed `/tmp/davdeploy-nova-asg-486/create-fresh.tfplan`
  with `AWS_PROFILE=ai-platform-pilot-key`: nine creates, zero changes or
  deletes. The monitored apply `nova-asg-486-create-fresh-20261124` started at
  `2026-11-24T18:00:05Z`; completion and AWS checks are pending.

## Observed result

Pending. The credential-less attempt failed before mutation. The correctly
profiled monitored attempt is in progress; verify its terminal state before
recording any AWS resource outcome.

## Results

Pending.

## Teardown

Destroy through `scripts/terraform_run_monitor.py`. Retain local state artifacts
and do not commit state files. Independently verify the exact ASG, launch
template, VPC, subnets, route table, security group, instances, and volumes are
absent or terminated. Distinguish retained AWS instance history from active
resources.

## Final boundary

This test can prove the exact launch-template root-volume settings, EBS volume
encryption, ASG health, EC2 system/instance checks, and teardown. It does not
prove guest application health, AMI provenance, instance-role scope, update or
failure recovery, complete cost, Nova remote-state enablement, Nova dispatch,
cross-account isolation, or customer deployment. The hosted control plane and
its state/locks remain untouched.
