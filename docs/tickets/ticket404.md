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

## Scope

- Inspect actual Terraform plan values and configuration references for
  `aws_eks_node_group` resources.
- Require a unique same-plan `aws_launch_template` reference for each planned
  node group; deny missing, ambiguous, external, malformed, or unknown bindings.
- Reuse existing launch-template metadata checks and fail closed when token
  requirements are not `required`.
- Keep runtime feature gates unchanged. This is source policy only and does not
  enable EKS planning or execution.

## Acceptance criteria

- [ ] Existing secure plans remain accepted for human review.
- [ ] EKS groups with a same-plan launch template requiring IMDSv2 pass this
  check.
- [ ] Missing, external, ambiguous, unknown, or insecure launch-template
  bindings are denied with safe findings.
- [ ] Nested Terraform module configuration is handled, or explicitly rejected
  when the binding cannot be proven.
- [ ] Focused tests, full verification, documentation conventions, diff checks,
  and all required CI pass.
- [ ] Update the capability evidence matrix to describe the bounded check and
  its limits. No hosted EKS plan or workload is claimed.

## References

- [Amazon EKS security best practices: node IMDS configuration](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)
- [Customize managed nodes with launch templates](https://docs.aws.amazon.com/eks/latest/userguide/launch-templates.html)
