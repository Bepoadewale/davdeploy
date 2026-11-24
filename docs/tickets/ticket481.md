# ticket481

PR: [#481 — feat: bind EFS NFS rules to mount targets](https://github.com/Bepoadewale/davdeploy/pull/481) (draft)
Branch: `feat/efs-mount-target-binding-481`

## Problem / goal

The generated-plan policy requires NFS ingress to use exactly TCP/2049 from a
security-group source, but it does not verify that the ingress rule targets a
security group attached to an EFS mount target. A safe source group and port
alone do not show that NFS reaches the intended mount target. Bind each planned
EFS mount target to a same-plan security group and require every planned NFS
ingress target to use one of those mount-target groups.

## Current repo state

- Backend `main` is `63e9276cf1eeb692464d895b9730a6a3ea7c4138` (PR #480).
- PR #477 requires encrypted EFS, General Purpose performance, Bursting
  throughput, and exact TCP/2049 ingress from a security-group source.
- The module attaches its EFS security group to mount targets and targets that
  group from NFS ingress, but current policy does not bind these relationships.
- AWS states that mount-target security groups must allow inbound NFS 2049 from
  client security groups. No EFS resource or hosted control-plane change is
  required for this source-only package.

## Research / references used

- [AWS EFS security group network access](https://docs.aws.amazon.com/efs/latest/ug/network-access.html)
- [Terraform `aws_efs_mount_target`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/efs_mount_target)
- [Terraform JSON output format](https://developer.hashicorp.com/terraform/internals/json-format)
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/efs-shared-storage/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Work planned for the PR

1. Bind each EFS mount target's configured `security_groups` references to
   same-plan security-group resources.
2. Require each NFS ingress target to match a group attached to a planned EFS
   mount target; fail closed on missing, unknown, unrelated, or mismatched
   target references.
3. Add regression tests for the accepted reference chain and missing/mismatched
   targets, then update the evidence matrix with remaining mount and file-access
   limitations.

## Acceptance criteria

- [ ] Policy accepts a same-plan EFS file system, mount target, mount-target
  security group, and exact NFS ingress target/source relationship.
- [ ] Policy denies an ingress rule aimed at a different security group and
  mount targets with missing, unknown, or non-same-plan security-group binding.
- [ ] Existing exact TCP/2049, security-group source, and EFS encryption/mode
  requirements remain enforced.
- [ ] Findings do not expose plan values and tests cover accepted and rejected
  bindings.
- [ ] Evidence matrix states that source policy still does not prove mounted
  file read/write, tenant authorization, lifecycle, pricing, or Nova dispatch.
- [ ] No AWS or hosted control-plane resource is changed.
- [ ] Local verification, ticket conventions, diff checks, and all seven CI
  checks pass before merge.

## Acceptance status

Ticket-first bootstrap is present. Implementation and verification are pending.
No AWS or hosted control-plane resource has been changed.

## Tests / validation performed

Pending implementation.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket481.md`

## Boundaries

Source and documentation only. Do not modify AWS resources, the hosted control
plane, or existing audit evidence. Do not claim EFS file access or lifecycle
from plan-policy tests.

## Follow-up work

Direct isolated EFS lifecycle evidence must separately verify client mount and
authorized file operations, denied access where applicable, teardown, and
independent absence. Pricing and Nova-hosted execution remain separate gates.
