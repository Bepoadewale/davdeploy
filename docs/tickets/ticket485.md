# ticket485

PR: [#485 — feat: validate EC2 Auto Scaling lifecycle](https://github.com/Bepoadewale/davdeploy/pull/485) (open)
Branch: `feat/autoscaling-lifecycle-485`

## Problem / goal

PR #483 bounds the generated Auto Scaling plan but has no active-instance
lifecycle evidence. Validate the exact bounded `t3.micro`/Amazon Linux 2023/
IMDSv2 profile in a fresh same-account customer-side environment, without
using or changing the hosted control plane. Keep the Terraform state local and
the network isolated, then tear down the test stack and independently verify
absence.

## Current repo state

- Backend `main` starts from commit `8ff3061f34e10d5bf824a23bc71f8099d0e6e58f`
  (PR #484).
- PR #483's bounded Auto Scaling module and generated-plan policy are merged.
- The AWS caller was verified as account `654654474502` in `us-east-1`.
- Before the test, no `nova-asg-485` Auto Scaling group or EC2 instance existed.
- The account currently has the platform database VPC and default VPC; the
  test must create a dedicated, non-overlapping VPC with no internet gateway,
  NAT gateway, public IP, or ingress rule.
- The test has since been destroyed: no test ASG, launch template, VPC,
  subnets, route table, or security group remain. Both launched instance
  records are terminated; local Terraform state lists zero resources.
- The run monitor has 46 records and no active operation.
- Hosted control-plane state, locks, runtime, and endpoints are out of scope.

## Research / references used

- [Terraform AWS Auto Scaling Group resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/autoscaling_group)
- [Terraform AWS security group resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group)
- [EC2 instance status checks](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-system-instance-status-check.html)
- `infrastructure/terraform/modules/ec2-autoscaling/main.tf`
- `apps/api/src/davdeploy/generated_plan_policy.py`

## Work planned for the PR

1. Add a narrowly scoped test root using local Terraform state and unique
   `TestId=nova-asg-485` tags.
2. Create only a dedicated VPC, isolated subnets, a security group with no
   ingress/egress, one bounded Auto Scaling group and launch template, and at
   most two `t3.micro` instances using Amazon Linux 2023 with IMDSv2.
3. Record apply, instance/ASG health, a bounded capacity change, and teardown
   evidence in `docs/test/test485.md`. Do not claim application health, Nova
   dispatch, or hosted execution.
4. Destroy through `scripts/terraform_run_monitor.py`, retain the local state
   file as evidence, and independently query AWS for absence.
5. Reconcile the EC2 Auto Scaling row in the Nova capability evidence matrix.

## Acceptance criteria

- [x] The test root is isolated from all existing VPCs and has no public route,
  public address, inbound rule, or general internet egress.
- [x] Plan/apply uses a fresh local state file and only creates the tagged test
  resources; no remote backend, hosted control-plane request, or Nova apply is
  involved.
- [x] ASG desired capacity is observed at one and two and returned to one;
  instance status checks and ASG lifecycle state are recorded without exposing
  credentials or customer data.
- [x] The stack is destroyed through the Terraform run monitor and AWS
  independently confirms the group, launch template, and network resources
  absent; both EC2 instance records are terminated with no attached volumes.
- [x] The evidence and matrix state the exact behavior proved and retain gaps
  for application health, image provenance, update/recovery, complete price,
  Nova dispatch, and cross-account isolation.
- [x] Documentation conventions, Terraform formatting/validation, reviewed
  plan, `git diff --check`, and all required CI checks pass before merge.
- [x] No hosted control-plane resource or state is changed; protected local
  files and existing audit evidence remain untouched.

## Boundaries

This is an isolated same-account service test, not a customer deployment or
Nova certification. It may create temporary test AWS resources in account
`654654474502`, region `us-east-1`, only under the exact test prefix and tags
above. The hosted control plane and its state/lock resources must not be
changed. Do not delete the retained local Terraform state or any unrelated
resource or file.

## Acceptance status

Isolated AWS lifecycle evidence is complete. All seven required checks passed
on implementation/evidence commit `223eab9ab972cf40b099077293ab407e0c8bc7d6`
in run `45447414384`; the status-reconciliation commit
`87803725c2f8528467d4b16d9f4cde877aa5a843` also passed all seven checks in
run `45448665281`. This follow-up records that result and is receiving its
own CI run before merge.

## Tests / validation performed

- `terraform fmt -check -recursive docs/test/fixtures/nova-asg-485` — passed.
- `terraform -chdir=docs/test/fixtures/nova-asg-485 validate` — passed.
- Reviewed creation plan — nine creates, zero changes/destroys, zero security
  group rules.
- Reviewed capacity-two and scale-back plans — one in-place ASG update each.
- Reviewed teardown plan — nine deletes, zero creates/updates.
- `GITHUB_PR_NUMBER=485 .venv-pr399/bin/python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Initial draft PR commit reported no checks. The implementation/evidence head
  passed all seven PR checks in run
  [45447414384](https://github.com/Bepoadewale/davdeploy/actions/runs/45447414384).
- The status-reconciliation commit passed all seven checks in run
  [45448665281](https://github.com/Bepoadewale/davdeploy/actions/runs/45448665281).

## Evidence files produced

- `docs/test/fixtures/nova-asg-485/`
- `docs/test/test485.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket485.md`

## Follow-up work

Keep application health, AMI provenance, update/recovery, complete pricing,
cross-account isolation, and Nova dispatch as separate open evidence gates.
