# ticket402 — enforce EC2 instance metadata protections in generated plans

PR: pending draft PR creation
Branch: `feat/nova-instance-metadata-policy-402`

## Problem / goal

The Nova actual-plan policy has no bounded check for EC2 Instance Metadata
Service (IMDS) settings on planned instances and launch templates. Require
known metadata configuration and require IMDSv2 tokens whenever the endpoint
is enabled. This is a plan-policy check only; it must not enable an executor.

## Current repo state

Backend `main` is `4bd4c55` after PR #400. PR #401 is a separate open draft for
network ACL ingress policy and is not merged. Generated-plan policy still has
coverage gaps across catalogue modules and Terraform roots. Nova exact-plan
apply remains a separate draft and is not available; trusted pricing is held.
No Nova workload has been applied or certified.

## Research / references used

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- AWS EC2 Instance Metadata Service configuration documentation
- Terraform AWS provider documentation for `aws_instance` and
  `aws_launch_template`

## Work planned for the PR

- Inspect actual plan values and unknown metadata for
  `aws_instance.metadata_options` and `aws_launch_template.metadata_options`.
- Deny missing, malformed, or policy-critical unknown metadata settings.
- Require `http_tokens = "required"` when `http_endpoint = "enabled"`; allow
  an explicitly disabled endpoint.
- Add negative, positive, and unknown-value regression cases and update the
  finite capability evidence matrix.
- Keep all execution feature gates unchanged and make no AWS calls or changes.

## Acceptance criteria

- [ ] Planned instances and launch templates with enabled IMDS require
      `http_tokens = "required"`.
- [ ] Explicitly disabled IMDS endpoints remain eligible if all relevant
      values are known.
- [ ] Missing, malformed, or policy-critical unknown settings fail closed.
- [ ] Focused tests, full verification, docs convention, diff checks, and
      required hosted CI pass.
- [ ] No AWS resource is created, updated, or deleted.

## Acceptance status

Not started. This ticket is the draft-PR bootstrap and will be updated with
implementation and evidence.

## Tests / validation performed

Bootstrap only; no implementation tests have been run.

## Evidence files produced

Pending: `docs/test/test402.md`.

## Boundaries

This does not validate metadata access from the guest, instance profiles,
network reachability, image hardening, or end-to-end VM safety. It does not
establish policy coverage for EKS nodes, Auto Scaling launch templates beyond
the listed planned Terraform resource values, or every compute resource type.
No AWS workload or apply is part of this change.

## Follow-up work

Continue the finite policy map for compute, identity, storage, network, and
other catalogued resource families; keep execution gated on trusted pricing and
the remaining apply/health/lifecycle evidence.
