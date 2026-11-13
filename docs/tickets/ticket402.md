# ticket402 — enforce EC2 instance metadata protections in generated plans

PR: https://github.com/Bepoadewale/davdeploy/pull/402 (open draft)
Branch: `feat/nova-instance-metadata-policy-402`

## Problem / goal

The Nova actual-plan policy has no bounded check for EC2 Instance Metadata
Service (IMDS) settings on planned instances, launch templates, or legacy
launch configurations. Require known metadata configuration and require
IMDSv2 tokens whenever the endpoint is enabled. Also require regional EC2
metadata defaults to prefer IMDSv2. Account defaults can be overridden by
launch-specific settings, so per-resource checks remain required. This is a
plan-policy check only; it must not enable an executor.

## Current repo state

Backend `main` is `4bd4c55` after PR #400. PR #401 is a separate open draft for
network ACL ingress policy and is not merged. Generated-plan policy still has
coverage gaps across catalogue modules and Terraform roots. Nova exact-plan
apply remains a separate draft and is not available; trusted pricing is held.
No Nova workload has been applied or certified.

## Research / references used

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- [Configure EC2 Instance Metadata Service options](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-options.html)
- [Configure metadata options for new EC2 instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-IMDS-new-instances.html)
- [Terraform `aws_launch_configuration`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/launch_configuration)
- [Terraform `aws_ec2_instance_metadata_defaults`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ec2_instance_metadata_defaults)
- [Terraform `aws_instance`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance)
- [Terraform `aws_launch_template`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/launch_template)

## Work planned for the PR

- Inspect actual plan values and unknown metadata for `metadata_options` on
  `aws_instance`, `aws_launch_template`, and `aws_launch_configuration`.
- Require `http_tokens = "required"` for
  `aws_ec2_instance_metadata_defaults`; document that defaults do not enforce
  instance settings that explicitly override them.
- Deny missing, malformed, or policy-critical unknown metadata settings.
- Require `http_tokens = "required"` when `http_endpoint = "enabled"`; allow
  an explicitly disabled endpoint.
- Treat `http_tokens` as a policy enum rather than credential material in the
  structured proposal validator; policy still rejects unsafe values.
- Add negative, positive, and unknown-value regression cases and update the
  finite capability evidence matrix.
- Keep all execution feature gates unchanged and make no AWS calls or changes.

## Acceptance criteria

- [x] Planned instances, launch templates, and launch configurations with enabled IMDS require
      `http_tokens = "required"`.
- [x] Regional metadata defaults require `http_tokens = "required"`; explicit
      optional/no-preference and unknown values fail closed.
- [x] Explicitly disabled IMDS endpoints remain eligible if all relevant
      values are known.
- [x] Missing, malformed, or policy-critical unknown settings fail closed.
- [x] Focused tests, full verification, docs convention, and diff checks pass.
- [ ] Hosted CI passes for the expanded implementation and evidence revision.
- [x] No AWS resource is created, updated, or deleted.

## Acceptance status

The original implementation and evidence revisions are locally and remotely
verified. The expanded launch-configuration and regional-default coverage
passes local focused and full verification; hosted CI is pending for this
revision. The draft stays open.

## Tests / validation performed

Focused plan-policy and structured-proposal suites passed (222 total). Full
verification passed with 1,111 tests; documentation conventions and diff
checks are being refreshed. Hosted CI runs `43502219872` and `43503068011`
passed all seven jobs for the earlier revision; the expanded revision still
requires CI. Exact commands are recorded in `docs/test/test402.md`.

## Evidence files produced

`docs/test/test402.md` records local source and test evidence; no AWS workload
test occurred.

## Boundaries

This does not validate metadata access from the guest, instance profiles,
network reachability, image hardening, or end-to-end VM safety. Regional
metadata defaults are defaults, not an account-wide enforcement mechanism;
launch-specific overrides still need their own planned-resource checks. It
does not establish policy coverage for EKS nodes, Auto Scaling groups as a
whole, or every compute resource type. No AWS workload or apply is part of
this change.

## Follow-up work

Continue the finite policy map for compute, identity, storage, network, and
other catalogued resource families; keep execution gated on trusted pricing and
the remaining apply/health/lifecycle evidence.
