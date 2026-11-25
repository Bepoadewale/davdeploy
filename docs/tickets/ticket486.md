# ticket486

PR: [#486 — feat: require encrypted Auto Scaling root volumes](https://github.com/Bepoadewale/davdeploy/pull/486)
Branch: `feat/autoscaling-ebs-bounds-486`

## Problem / goal

PR #483 bounds the Auto Scaling profile and requires IMDSv2, but its launch
template leaves the root EBS volume settings implicit. Explicitly require an
encrypted, bounded gp3 root volume that is deleted when its instance
terminates, and reject plans where the mapping is missing, unknown, or unsafe.
Verify the exact module shape in a fresh same-account test without touching
the hosted control plane.

## Current repo state

- Backend `main` is `9680e6ff0d7637b9dc56948c3154126ef052afd4` (merged PR #498), which adds source-only AWS Batch bounds. The PR #486 branch now includes this mainline; the sync changes no AWS or hosted control-plane state.
- PR #483's generated-plan policy checks ASG capacity, launch-template
  binding, instance type, AMI-ID shape, and IMDSv2. This PR adds verified AMI
  root-device binding and bounded encrypted root EBS settings.
- PR #485 records isolated capacity 1→2→1 evidence with EC2 status checks;
  its test did not verify root-volume encryption.
- AWS account `654654474502`, region `us-east-1`; hosted control-plane
  resources and state remain outside scope.

## Research / references used

- [Terraform AWS launch template resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/launch_template)
- [AWS launch-template block device mappings](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/block-device-mapping-concepts.html)
- `infrastructure/terraform/modules/ec2-autoscaling/main.tf`
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`

## Work planned for the PR

1. Add one EBS mapping for the selected AMI's verified root device: encrypted,
   gp3, 8 GiB, and delete-on-termination.
2. Require that exact known root-volume profile in generated ASG plans and
   fail closed for missing, unknown, multiple, or unsafe mappings.
3. Add regression tests for acceptance, unknown values, unencrypted volumes,
   wrong device/type/size, and retained-on-termination settings.
4. Apply the module in a new isolated local-state customer test root; verify
   ASG/EC2 health and the attached volume's encryption/termination settings,
   then destroy and independently verify cleanup.
5. Reconcile resource-family and goal status without claiming Nova dispatch.
6. Bind the launch template's AMI ID and device mapping to the same planned
   `aws_ami` root-device metadata; fail closed if the source or metadata is
   missing or unknown.

## Acceptance criteria

- [x] Module plans explicitly select the selected AMI's actual root device,
  encrypted gp3 8 GiB root storage, and delete-on-termination.
- [x] Generated-plan policy binds the image and root mapping to one known
  `aws_ami` metadata source and denies mismatched or unknown root devices.
- [x] Generated-plan policy accepts the exact shape and denies missing,
  unknown, unencrypted, oversized, wrong-device/type, or retained mappings.
- [x] Regression tests cover the accepted and rejected shapes with redacted
  findings.
- [x] A fresh isolated AWS test verifies the running instance's EBS volume is
  encrypted, the ASG is healthy, and termination removes the volume.
- [x] Both isolated test cycles were destroyed through the Terraform run monitor; the ASG,
  launch template, and network are independently absent and instance records
  are terminated.
- [x] Evidence keeps AMI provenance, instance-role scope, guest health,
  update/recovery, full pricing, remote Nova state, and Nova dispatch as
  separate open gates.
- [x] The required clean-room validation completed its final clean step after
  explicit approval; the isolated generated artifacts and Compose resources
  were removed and independently verified absent.
- [x] Docs conventions, focused/full verification, Terraform formatting and
  validation, `git diff --check`, and all required CI checks pass on the final
  synchronized code/status head before merge.
- [x] No hosted control-plane resource or state changes; protected local files
  and lineage evidence remain untouched.

## Boundaries

Only fresh resources tagged for `nova-asg-486` may be created in account
`654654474502`, region `us-east-1`. Use an isolated VPC with no public route,
public IP, ingress, or internet egress, and local Terraform state. Do not
change the hosted control plane, remote state, unrelated AWS resources, or
protected local files. Retain local state artifacts after teardown.

## Acceptance status

Automated review found that a hard-coded `/dev/xvda` does not prove it is the
selected AMI's root device, and required the clean-room gate for Terraform
behavior. The implementation now queries `aws_ami` metadata and binds the
image ID and root mapping to that source. Two fresh isolated AWS cycles passed
and were destroyed with independent absence checks. Regression tests cover
planned AMI metadata taking precedence over stale prior state. The isolated
clean-room cycle passed all demos and `make verify` (1,752 tests); after
explicit approval, its final `make clean-local` completed and the approved
generated artifacts were verified absent. Both prior review findings are
addressed. The branch now includes current `main` (`b6b663d`) through merge
commit `05a6e5c`. All seven checks passed on pre-cleanup documentation head
`227c62a` in CI run `45589122723`; new documentation updates require fresh
final-head checks. The current policy suite passes 604 tests, and Ruff,
documentation conventions, and `git diff --check` pass locally. No hosted
control-plane resource or AWS resource was changed by synchronization or
cleanup.

## Tests / validation performed

- `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest -p
  no:cacheprovider tests/test_generated_plan_policy.py -q`: 544 passed after
  synchronizing with PR #498.
- `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/ruff check
  apps/api/src/davdeploy/generated_plan_policy.py
  tests/test_generated_plan_policy.py`: passed after synchronization.
- `GITHUB_PR_NUMBER=486 python3 scripts/check_doc_conventions.py` and
  `git diff --check`: passed after synchronization.
- `.venv/bin/python -m pytest -q tests/test_generated_plan_policy.py -k
  autoscaling`: 42 passed, 481 deselected (before synchronization).
- `make verify`: passed (1,752 tests after the AMI-root binding change; one
  existing Starlette/httpx deprecation warning; OpenAPI snapshot and Compose
  configuration passed).
- `.venv/bin/python -m pytest tests/test_generated_plan_policy.py -k
  'autoscaling_planned_ami_metadata_takes_precedence_over_prior_state or
  autoscaling_root_device'`: 4 passed, 519 deselected.
- `.venv/bin/ruff check apps/api/src/davdeploy/generated_plan_policy.py
  tests/test_generated_plan_policy.py`: passed.
- `terraform -chdir=docs/test/fixtures/nova-asg-486 fmt -check -recursive`:
  passed.
- `terraform -chdir=docs/test/fixtures/nova-asg-486 validate`: passed.
- `GITHUB_PR_NUMBER=486 .venv-pr399/bin/python
  scripts/check_doc_conventions.py`: passed.
- Reviewed saved plan `/tmp/davdeploy-nova-asg-486/create-fresh.tfplan`: nine
  creates, zero updates or deletes. It specifies one `/dev/xvda` mapping with
  `encrypted=true`, `delete_on_termination=true`, gp3, and 8 GiB.
- AWS observed the ASG `Healthy` / `InService`, EC2 instance and system checks
  `ok`, IMDSv2 required, and no public IP. The attached root volume was
  encrypted, 8 GiB gp3, and delete-on-termination.
- The reviewed destroy plan contained exactly nine deletes. Monitored destroy
  run `nova-asg-486-destroy-20261124` succeeded; independent AWS checks found
  the ASG, launch template, VPC, subnets, route table, security group, and
  volume absent. The instance is terminated, Terraform state lists zero
  resources, and the Terraform run monitor has zero active operations.
- Cycle two's reviewed destroy plan also contained exactly nine deletes, zero
  creates, updates, or replacements. Monitored run
  `nova-asg-486-destroy-cycle2-20261124` (Terraform PID `95699`) succeeded.
  Both test instances are terminated; all tagged resources, the specific root
  volume, and the Auto Scaling group are absent; Terraform state and active
  monitor operations are empty.
- PR checks run `45504483123`: all seven checks passed on synchronized head
  `d20a599`.
- AWS `aws_ami` data lookup for this test returned AMI
  `ami-0aacbf72109c53c0c`, root device `/dev/xvda`; the refreshed plan contains
  that metadata in `prior_state` and references it from the image and device
  mapping expressions.
- Isolated clean-room worktree `/private/tmp/davdeploy-pr486-cleanroom-20261124`
  based on `d6c8585`, with the current policy and regression test synchronized,
  used Compose project
  `davdeploy-pr486-cleanroom-20261124`. Initial `make clean-local` passed with
  no prior artifacts or project containers/volumes. `make bootstrap-local`,
  smoke, API contract, local customer-plan E2E, fixture seeding, simple/complex/
  degraded/Day-2 demos, policy-failure/readiness-failure demos, trace check,
  and `make verify` all passed (1,752 tests). After explicit approval,
  `make clean-local` completed. The `.venv`, `.local`, project containers,
  Compose volume, and network are absent; the isolated worktree remains.

## Evidence files produced

- `infrastructure/terraform/modules/ec2-autoscaling/main.tf`
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/test/fixtures/nova-asg-486/`
- `docs/test/test486.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket486.md`

## Follow-up work

Keep AMI provenance, instance-role permissions, workload health, update and
failure recovery, complete cost, Nova remote-state configuration, and Nova
dispatch as separate gates.

## Current-main synchronization — 2026-11-25

The PR branch was synchronized with backend `main` at
`b6b663d87c7f31bebd2baf47f4589d8205ec2b3f` in merge commit `05a6e5c`.
The AMI root-device binding and its regression tests remain present after the
merge. Focused Auto Scaling policy tests passed (42 passed, 562 deselected);
Ruff, documentation conventions, and `git diff --check` passed. Earlier CI
run `45545915711` covers the previous PR head only; fresh final-head CI and
review are required after this synchronization.

The isolated clean-room run completed bootstrap, smoke, simple/complex and
degraded/Day-2 demos, policy/readiness failure checks, trace checks, and
`make verify` (1,752 tests). After explicit approval, `make clean-local`
completed; the generated `.venv`, `.local`, project containers, Compose volume,
and network are absent. The worktree itself remains. No AWS workload or hosted
control-plane resource was changed by this source synchronization or cleanup.
