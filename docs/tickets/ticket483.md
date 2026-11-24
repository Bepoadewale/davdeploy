# ticket483

PR: [#483 — feat: bound Auto Scaling plans](https://github.com/Bepoadewale/davdeploy/pull/483) (draft)
Branch: `feat/autoscaling-plan-bounds-483`

## Problem / goal

Generated-plan policy checks IMDSv2 on launch templates but does not bound
Auto Scaling Group (ASG) capacity or require a same-plan launch template. The
module also selects `$Latest`, which can change as launch-template versions
are added. Define and enforce one small ASG shape: at most three `t3.micro`
instances, a known AMI ID, IMDSv2 required, and one same-plan launch template
whose version is explicitly referenced through `latest_version`.

## Current repo state

- Backend `main` is `1ee1c67d9624599959cd07da231347538382138b` (PR #482).
- `modules/ec2-autoscaling` creates an ASG using a same-module launch template,
  but selects `$Latest` and has caller-selectable instance type and capacity.
- Existing source policy checks launch-template IMDSv2 settings but not ASG
  capacity bounds or template binding.
- No AWS instance or ASG is created by this source-only package.

## Research / references used

- [Terraform `aws_autoscaling_group`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/autoscaling_group)
- [Terraform `aws_launch_template`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/launch_template.html)
- [AWS launch-template version selection](https://docs.aws.amazon.com/autoscaling/ec2/userguide/migrate-to-launch-templates.html)
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/ec2-autoscaling/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Work planned for the PR

1. Require known ASG minimum, desired, and maximum capacities satisfying
   `0 <= min <= desired <= max <= 3`.
2. Require exactly one same-plan launch template, and use its
   `latest_version` reference instead of dynamic `$Latest`/`$Default` strings.
3. Pin the reviewed profile to `t3.micro`, require a known AMI ID and IMDSv2,
   and deny unsupported mixed-instance/launch-configuration shapes.
4. Add regression coverage and record that runtime, AMI provenance, volume
   encryption, price, and lifecycle are separate evidence gaps.

## Acceptance criteria

- [x] Policy accepts a known bounded ASG and its same-plan launch-template
  reference to `latest_version`.
- [x] Policy denies unknown or out-of-range capacity, an external/missing or
  multiple launch templates, dynamic `$Latest`/`$Default`, and unsupported
  mixed-instance or launch-configuration profiles.
- [x] The launch template must use `t3.micro`, a known AMI ID, and IMDSv2.
- [x] Tests cover the accepted shape, unsafe capacities, unknown values,
  external references, dynamic template versions, and finding redaction.
- [x] The matrix retains AMI provenance, volume encryption, ongoing instance
  hours, workload health, update/recovery, teardown, and Nova execution gaps.
- [x] No AWS, remote Terraform state, or hosted control-plane resource changes.
- [ ] Local verification, docs conventions, `git diff --check`, and all seven
  CI checks pass before merge.

## Acceptance status

Implementation and local policy validation are complete. The final PR head
still needs seven passing CI checks before this draft can be considered for
review. No AWS, Terraform state, or hosted control-plane resource has changed.

## Tests / validation performed

- `PYTHONPATH=apps/api/src .venv-pr399/bin/python -m pytest -q tests/test_generated_plan_policy.py -k autoscaling` — 21 passed.
- `PYTHONPATH=apps/api/src .venv-pr399/bin/python -m pytest -q tests/test_generated_plan_policy.py` — 502 passed.
- `make verify` — passed: 1,731 tests, Actions configuration, Ruff, OpenAPI, and Docker Compose checks; one existing Starlette/httpx deprecation warning.
- `.venv-pr399/bin/ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py` — passed.
- `terraform fmt -check infrastructure/terraform/modules/ec2-autoscaling/main.tf` — passed.
- Offline `terraform init -backend=false -input=false -lockfile=readonly` could not install AWS provider v5.100.0 because the provider registry connection failed; `terraform validate` then passed using the existing local provider cache.
- `GITHUB_PR_NUMBER=483 .venv-pr399/bin/python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- PR CI run 45391202592 passed all seven checks on `999fd06`. The final head adds one test-only regression for two same-plan templates; CI for that final head remains pending.
- The full local clean-room demo cycle was not run because its `clean-local` target deletes `.venv` and `.local`, and the current session's deletion boundary protects local files. The final PR's fresh-runner CI remains required.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/ec2-autoscaling/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket483.md`

## Boundaries

Source and documentation only. Do not create or change AWS resources, remote
Terraform state, or hosted control-plane resources. Do not claim that a bounded
ASG plan proves workload health, AMI provenance, instance costs, lifecycle, or
Nova execution.

## Follow-up work

Price ongoing instance-hours and related volumes/networking, verify AMI
provenance and storage encryption, and collect isolated application health,
update/recovery, teardown, and independent absence evidence for an accepted
instance type and region.
