# test485 — Isolated EC2 Auto Scaling lifecycle

Date: 2026-11-24

Execution type: Direct Terraform in the owner-controlled same-account customer
test boundary. This does not use Nova or the hosted control plane.

Repository: `Bepoadewale/davdeploy`.

Customer repository: None; direct same-account AWS service test.

Commit: `21727918b2360343108dd9bfaa4f517d0c384e00` (test fixture applied).

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
- All tag-capable managed resources tagged `TestId=nova-asg-485`.
- Local Terraform state only. No hosted API, worker, remote state, lock table,
  Nova dispatch, customer data, or application endpoint.

## Resources created

The reviewed creation plan contained nine resources: one VPC, two subnets, one
route table, two route-table associations, one security group, one launch
template, and one Auto Scaling group. It contained no destroy or update
actions. The plan specified zero security-group ingress and egress rules. All
nine resources were created successfully.

## Commands executed

- Verified AWS account `654654474502` and region `us-east-1`.
- Confirmed the exact `nova-asg-485` Auto Scaling group and EC2 instance
  inventory was empty before planning.
- Confirmed the Terraform run monitor had zero active operations.
- `terraform fmt -check -recursive docs/test/fixtures/nova-asg-485` passed.
- `terraform validate` passed for the local-state test root.
- Reviewed plan: nine creates, zero changes, zero destroys; zero security-group
  ingress and egress rules.
- The initial apply completed successfully: run
  `nova-asg-485-create-20261124`, Terraform PID `53024`, log path
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-asg-485-create-20261124.log`.
- AWS reported ASG min/desired/max `1/1/2`; its one `t3.micro` instance
  `i-0d3dd6151c3cd7f99` was `Healthy` / `InService`. EC2 instance and system
  status checks both returned `ok`; the instance had no public IP and required
  IMDSv2 tokens.
- The dedicated security group had zero rules. Both test VPC route tables had
  only the local route.
- Capacity-two plan: one in-place ASG update, zero other resource changes and
  zero deletes. The monitored scale-up completed successfully as run
  `nova-asg-485-scale-2-20261124`, Terraform PID `55002`, with log path
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-asg-485-scale-2-20261124.log`.
- At capacity two, AWS reported min/desired/max `2/2/2`; both `t3.micro`
  instances were `Healthy` / `InService`, and both EC2 instance and system
  status checks returned `ok`. Neither instance had a public IP and both
  required IMDSv2 tokens.
- Capacity-one plan: one in-place ASG update, zero other resource changes and
  zero deletes. Scale-back completed as monitored run
  `nova-asg-485-scale-1-20261124`, Terraform PID `56684`, with log path
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-asg-485-scale-1-20261124.log`.
- After scale-back, AWS again reported min/desired/max `1/1/2`, with one
  `Healthy` / `InService` instance and no public IP.

## Observed result

AWS observed the ASG desired capacity at one, then two, then one. At capacity
one the sole instance was `Healthy` / `InService`, with EC2 instance and system
checks `ok`. At capacity two both instances had those same healthy states and
both EC2 checks were `ok`. The profile stayed at `t3.micro`, max capacity two,
IMDSv2 required, with no public IP, security-group rules, or non-local VPC
routes. This proves the service-level capacity lifecycle and EC2 status checks
for this exact shape; it does not prove guest application health.

## Results

The initial plan and apply created nine resources. Scale-up and scale-back
each made one in-place ASG update with no additions or deletes. The group
returned to desired capacity one before teardown.

## Teardown

The reviewed teardown plan contained exactly nine deletes and no additions or
updates. The first monitored attempt, `nova-asg-485-destroy-20261124` (PID
`58033`), exited before any AWS mutation because Terraform does not accept a
saved destroy plan through `terraform destroy`; it requires `terraform apply`
with that plan. The same plan then completed successfully through monitored
run `nova-asg-485-destroy-apply-20261124` (PID `59497`).

Independent AWS checks found the ASG absent, both test instances terminated,
and the VPC, both subnets, security group, route table, and launch template
absent. No volumes remained attached to either instance. The command
`terraform state list` returned zero resources; the local state file is
retained in this fixture and is not committed. The run monitor had 46 records
and zero active operations. AWS retains terminated instance records; they are
not active resources. Logs for both destroy attempts are under
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/`.

## Final boundary

The test can establish service lifecycle and EC2 system/instance status for
this exact shape. It does not establish guest application health, external
network access, AMI provenance, complete resource pricing, update/recovery
behavior, cross-account isolation, Nova authorization/dispatch, or a customer
deployment. The hosted control plane and its state/locks were untouched.
