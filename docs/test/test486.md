# test486 — Encrypted Auto Scaling root volume

Date: 2026-11-24

Execution type: Direct Terraform in the owner-controlled same-account customer
test boundary. This does not use Nova or the hosted control plane.

Repository: `Bepoadewale/davdeploy`.

Customer repository: None; direct same-account AWS service test.

Commit: Cycle 1 used `b348324`; cycle 2 uses `d6c8585` with the AMI-root
metadata binding fix.

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

The reviewed plan created nine resources: VPC `vpc-0e806bd2d5b31bcf7`, two
subnets (`subnet-02cede3cdc7ef69fe`, `subnet-0d17e0568020b79e2`), route table
`rtb-0f133560d80c00382`, two route-table associations, security group
`sg-0e74ec8ed63c66e70`, launch template `lt-0bf4282b398f04cbd`, and ASG
`davdeploy-nova-asg-486`. The ASG launched instance
`i-070ba188abdaf25b2` with root volume `vol-0174d4dd0b14672bc`.

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
  `No valid credential sources found`; Terraform PID `73211`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-asg-486-create-20261124.log`.
- The credentialed retry `nova-asg-486-create-keyprofile-20261124` failed
  before AWS changes because the saved plan was stale after local state
  metadata had been initialized; Terraform PID `75833`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-asg-486-create-keyprofile-20261124.log`.
- Refreshed and reviewed `/tmp/davdeploy-nova-asg-486/create-fresh.tfplan`
  with `AWS_PROFILE=ai-platform-pilot-key`: nine creates, zero changes or
  deletes. Monitored apply `nova-asg-486-create-fresh-20261124` started at
  `2026-11-24T18:00:05Z`, Terraform PID `78954`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-asg-486-create-fresh-20261124.log`;
  monitor result `SUCCEEDED`.
- AWS observed ASG min/desired/max `1/1/1`, with instance
  `i-070ba188abdaf25b2` `Healthy` / `InService`. It was `running`, type
  `t3.micro`, had no public IP, and required IMDSv2. EC2 instance and system
  status checks were both `ok`.
- AWS confirmed root device `/dev/xvda`, volume
  `vol-0174d4dd0b14672bc`, 8 GiB gp3, `Encrypted=true`,
  `DeleteOnTermination=true`, and attachment state `in-use`.
- The isolated security group had no ingress or egress rules. Both subnet
  `MapPublicIpOnLaunch` values were false, and the VPC route table had only
  its local route.
- The reviewed destroy plan contains exactly nine deletes and no creates,
  updates, or replacements. Monitored run `nova-asg-486-destroy-20261124`
  started at `2026-11-24T18:06:41Z`, Terraform PID `81609`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-asg-486-destroy-20261124.log`;
  monitor result `SUCCEEDED`.
- Independent AWS absence checks returned no ASG, launch template, VPC,
  subnet, route table, or security group tagged for this test. The EC2 record
  is `terminated`; no EBS volumes remain attached to it. Terraform state lists
  zero resources, and the run monitor has zero active runs.

## Observed result

The ASG and instance reached healthy service state. AWS verified the
encrypted 8 GiB gp3 root volume and its delete-on-termination setting. After
monitored teardown, the ASG, launch template, VPC, subnets, route table,
security group, and EBS volume were absent; the EC2 history record is
terminated. Terraform state lists zero resources. The local state artifact is
retained and is not committed.

## Results

ASG and EC2 infrastructure health, IMDSv2, network isolation, root EBS
settings, volume deletion, and cleanup passed for this exact test profile.

## Teardown

The reviewed destroy plan contained exactly nine deletes, zero creates,
updates, or replacements. Monitored run `nova-asg-486-destroy-20261124`
(Terraform PID `81609`) completed successfully. Independent AWS checks found
the ASG, launch template, VPC, subnets, route table, security group, and volume
absent; instance `i-070ba188abdaf25b2` is terminated. `terraform state list`
returned zero resources. Local state artifacts are retained and are not
committed. After synchronizing with PR #493, head
`9a6313a6074c37cdd4b9c0023452dc8710c5b428` passed all seven PR checks in run
[45531340170](https://github.com/Bepoadewale/davdeploy/actions/runs/45531340170).
The documentation-reconciliation head
`3d7fe8b89adb6fd6407afe989336a1d756e02d99` then passed all seven checks in
run `45532421344`. The completed local clean-room containers have been stopped; its generated
files, Compose volume, and network remain pending explicit cleanup approval.
The run log is
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-asg-486-destroy-20261124.log`.
AWS keeps the terminated instance history record; it is not active.

## Cycle 2 — AMI root-device binding

The second run exercises the reviewed fix: the module reads `aws_ami.root_device_name`
and uses it for the launch-template mapping. The fresh plan contains nine
creates, zero updates, and zero deletes. Its refreshed data-source state binds
AMI `ami-0aacbf72109c53c0c` to `/dev/xvda`, and both the launch-template image
ID and device-name expressions reference that same data source.

Monitored apply `nova-asg-486-create-cycle2-20261124` completed successfully;
Terraform PID `90936`, log
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-asg-486-create-cycle2-20261124.log`.
AWS observed ASG `davdeploy-nova-asg-486` at min/desired/max `1/1/1`, with
instance `i-0bbee566ffa755e9a` `Healthy` / `InService`. EC2 instance and system
status checks were `ok`. The `t3.micro` had no public IP and required IMDSv2.
AWS confirmed the AMI and instance root device were `/dev/xvda`, and attached
volume `vol-0d88cbcf3c59377cf` was encrypted, 8 GiB gp3, and configured to be
deleted on instance termination. The no-rule security group, local-only VPC
route, and non-public subnets were also verified.

The reviewed destroy plan contained exactly nine deletes, zero creates,
updates, or replacements. Monitored run `nova-asg-486-destroy-cycle2-20261124`
(Terraform PID `95699`) completed successfully; its log is
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-asg-486-destroy-cycle2-20261124.log`.
Independent checks found the test Auto Scaling group, launch template, VPC,
subnets, route table, security group, and volume absent. Instances
`i-070ba188abdaf25b2` and `i-0bbee566ffa755e9a` are terminated. Terraform state
lists zero resources and the run monitor has zero active operations. Local
state artifacts are retained and are not committed.

## Final boundary

This test can prove the exact launch-template root-volume settings, EBS volume
encryption, ASG health, EC2 system/instance checks, and teardown. It does not
prove guest application health, AMI provenance, instance-role scope, update or
failure recovery, complete cost, Nova remote-state enablement, Nova dispatch,
cross-account isolation, or customer deployment. The hosted control plane and
its state/locks remain untouched.
