# ticket477

PR: [#477 — feat: enforce bounded EFS plan safety](https://github.com/Bepoadewale/davdeploy/pull/477) (draft)
Branch: `feat/efs-plan-safety-477`

## Problem / goal

The shared EFS module enables encryption but relies on provider defaults for its
performance and throughput profile. Generated-plan policy currently does not
verify those settings and permits private CIDR-based NFS ingress. Make the
module's bounded storage profile explicit and require encrypted EFS with
General Purpose performance, Bursting throughput, and port 2049 access sourced
only from security groups.

## Current repo state

- `infrastructure/terraform/modules/efs-shared-storage/main.tf` creates an
  encrypted regional file system, mount targets, and NFS ingress from supplied
  application security groups.
- The matrix records EFS availability in `test244.md`, but no file read/write,
  access-denial, lifecycle, or full-cost evidence.
- This package is source-only. It will not create or change AWS resources or
  hosted control-plane resources.

## Research / references used

- [Terraform AWS provider `aws_efs_file_system` resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/efs_file_system)
- [AWS EFS file-system creation](https://docs.aws.amazon.com/efs/latest/ug/creating-using-create-fs.html)
- [AWS EFS throughput modes](https://docs.aws.amazon.com/efs/latest/ug/managing-throughput.html)
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/efs-shared-storage/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Work planned for the PR

1. Explicitly select `generalPurpose` performance and `bursting` throughput in
   the EFS module.
2. Deny generated plans with unknown or unsafe encryption, performance, or
   throughput values.
3. Require inbound NFS rules to use exactly TCP port 2049 and a security-group
   source; reject CIDR, prefix-list, broad-protocol, and unknown-source rules.
4. Add regression coverage for accepted, unsafe, and unknown values, and update
   the evidence matrix without overstating EFS functionality or cost evidence.

## Acceptance criteria

- [x] The module explicitly selects encryption, General Purpose performance,
  and Bursting throughput.
- [x] Generated-plan policy accepts the exact module shape and denies missing,
  unsafe, or unknown required EFS settings.
- [x] NFS ingress is restricted to TCP/2049 from a security-group source; CIDR,
  prefix-list, broad-port/protocol, and unknown-source forms are denied.
- [x] Regression tests cover accepted, unsafe, and unknown plan shapes without
  echoing caller values in findings.
- [x] The evidence matrix records this as source-only policy and leaves EFS
  file I/O, tenant isolation, lifecycle, hosted execution, and full regional
  price evidence open.
- [x] No AWS or hosted control-plane resource is changed.
- [ ] Focused tests, Ruff, Terraform format/validation, documentation
  conventions, `git diff --check`, and required GitHub checks pass. Local
  checks pass; required GitHub checks are pending.

## Acceptance status

Implementation and local validation are complete. The draft PR's required
GitHub checks and review remain pending. No AWS or hosted control-plane resource
has been changed.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/efs-shared-storage/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket477.md`

## Tests / validation performed

- `tests/test_generated_plan_policy.py -q` — 436 passed.
- `make verify` — passed: 1,665 tests, Actions configuration, Ruff, OpenAPI
  snapshot, and Docker Compose configuration. Pytest reported one existing
  Starlette/httpx deprecation warning.
- Ruff passed for the changed Python files.
- `terraform fmt -check -recursive infrastructure/terraform/modules/efs-shared-storage`
  — passed.
- `terraform -chdir=infrastructure/terraform/modules/efs-shared-storage init -backend=false -input=false`
  and `validate` — passed.
- `GITHUB_PR_NUMBER=477 .venv-pr399/bin/python scripts/check_doc_conventions.py`
  — passed.
- `git diff --check` — passed.
- Required GitHub checks have not run on the implementation head yet.

## Boundaries

Do not create or change EFS resources in this source-only package. Do not claim
file access, authorization, lifecycle, complete price, or Nova execution from
plan checks.

## Follow-up work

A separate isolated customer-side test must prove read/write and
unauthorized denial, update/failure recovery where applicable, teardown, and
independent absence; a price package must cover regional storage, throughput,
backup, and transfer assumptions.
