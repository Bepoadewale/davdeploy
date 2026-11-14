# ticket404 — verify EKS managed-node metadata in generated plans

PR: https://github.com/Bepoadewale/davdeploy/pull/404
Branch: `feat/nova-eks-imds-policy-404`

## Problem / goal

The shared generated-plan policy requires Instance Metadata Service Version 2
(IMDSv2) for explicit EC2 instances and launch templates, but it does not check
Amazon EKS managed node groups. A node group that uses an AWS-managed default
launch template does not expose its metadata settings in this plan. Do not
claim the node metadata is protected unless the plan contains a verifiable
same-deployment launch template with IMDSv2 required.

## Current repo state

Backend `main` includes PR #403 at `0e07f6b`. The existing policy covers
`aws_instance`, `aws_launch_template`, `aws_launch_configuration`, and
regional metadata defaults, but does not associate EKS managed node groups
with a launch template. Pricing remains held; hosted customer apply, health,
recovery, teardown, and composed execution remain unproven.

## Research / references used

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- [`NOVA_CAPABILITY_EVIDENCE_MATRIX.md`](../product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md)
- [Amazon EKS security best practices: node IMDS configuration](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)
- [Customize managed nodes with launch templates](https://docs.aws.amazon.com/eks/latest/userguide/launch-templates.html)
- [Terraform JSON plan and configuration format](https://developer.hashicorp.com/terraform/internals/json-format)

## Scope

- Inspect actual Terraform plan values and configuration references for
  `aws_eks_node_group` resources.
- Require a unique same-plan `aws_launch_template` reference for each planned
  node group; deny missing, ambiguous, external, malformed, or unknown bindings.
- Reuse existing launch-template metadata checks and fail closed when token
  requirements are not `required`.
- Keep runtime feature gates unchanged. This is source policy only and does not
  enable EKS planning or execution.

## Work planned for the PR

- Add a fail-closed association check between each planned EKS node group and
  its same-plan launch template.
- Reuse existing metadata enforcement and add synthetic positive/negative
  plan-policy coverage.
- Record source status and limits in the capability evidence matrix.

## Acceptance criteria

- [x] Existing secure plans remain accepted for human review.
- [x] EKS groups with a same-plan launch template requiring IMDSv2 pass this
  check.
- [x] Missing, external, ambiguous, unknown, or insecure launch-template
  bindings are denied with safe findings.
- [x] Nested Terraform module configuration is handled, or explicitly rejected
  when the binding cannot be proven.
- [x] Focused tests, full verification, documentation conventions, and diff
  checks pass.
- [x] All seven required checks pass for implementation commit `97a0c75` in
  [run `43529880000`](https://github.com/Bepoadewale/davdeploy/actions/runs/43529880000).
- [x] Update the capability evidence matrix to describe the bounded check and
  its limits. No hosted EKS plan or workload is claimed.

## References

- [Amazon EKS security best practices: node IMDS configuration](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)
- [Customize managed nodes with launch templates](https://docs.aws.amazon.com/eks/latest/userguide/launch-templates.html)

## Implementation status

The source check requires exactly one planned EKS launch-template object and
one or more configuration references, all of which must resolve to the same
planned `aws_launch_template` address. That launch template is checked by the
existing metadata policy and must require IMDSv2. A default EKS-managed or
external launch template is denied because its metadata settings are not
visible in this plan. Nested configuration resources are traversed according
to Terraform's `module_calls` plan format. Policy version is
`nova-generated-plan-2026-11-14.4`. Focused policy tests, full local
verification, isolated fixture proof, documentation convention checks, and
diff checks pass. Final-head CI is pending. The check is synthetic/source-only
and has not been deployed or exercised on a customer plan.

## Acceptance status

The policy code, focused tests, full local verification, isolated fixture
proof, documentation convention checks, diff checks, and capability-matrix
update are implemented. All seven required checks pass for implementation
commit `97a0c75` in run `43529880000`. No hosted EKS plan or customer workload
is claimed.

## Tests / validation performed

See [`test404.md`](../test/test404.md) for command output and the retained
isolated local proof resources.

## Evidence files produced

- `docs/tickets/ticket404.md`
- `docs/test/test404.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Boundaries

This PR changes source policy and evidence only. It does not enable EKS plan
execution, deploy a runtime change, create customer infrastructure, or prove
Kubernetes workload health.

## Follow-up work

Complete local documentation/diff checks and final-head CI. Separately close
the held pricing direction, exact-plan hosted apply, and EKS/customer lifecycle
acceptance in the private goal ledger.
