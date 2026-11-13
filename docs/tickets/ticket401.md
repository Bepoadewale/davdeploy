# ticket401 — inspect network ACL exposure in generated Terraform plans

PR: pending draft PR creation
Branch: `feat/nova-network-acl-policy-401`

## Problem / goal

The actual-plan policy checks public security-group ingress but does not inspect
AWS network ACL resources. Add bounded checks for inbound network ACL exposure
so an ACL cannot silently make administrative or data ports public. Preserve the
existing plan-only execution boundary.

## Current repo state

Backend main is `4bd4c55` (PR #400). Plan-level policy checks security groups,
public storage, databases, IAM, and selected invocation paths. Exact apply source
is separate and not deployed; trusted pricing remains held. No customer workload
has been applied or certified.

## Research / references used

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- [AWS Network ACLs](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-network-acls.html)
- [Terraform AWS network ACL rule resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/network_acl_rule)

## Work to be done

- Inspect actual plan values and unknown metadata for `aws_network_acl` and
  `aws_network_acl_rule` ingress rules.
- Deny malformed, incomplete, or policy-critical unknown ACL entries.
- Deny public inbound rules for configured administrative/data ports; require
  human review for public web/general ingress, including IPv4 and IPv6 sources.
- Add negative and valid scoped-network regression cases, update policy docs and
  PR test evidence. No cloud mutation or feature-gate change.

## Acceptance criteria

- [ ] Actual plans with malformed or critical unknown ACL ingress are denied.
- [ ] Public administrative/data ports are denied for IPv4 and IPv6 CIDRs.
- [ ] Public web/general ingress requires review; private/scoped ingress is not
      misclassified as public.
- [ ] Focused tests, full verification, docs convention, and required CI pass.
- [ ] No apply, deployment, or AWS resource mutation occurs.

## Validation and evidence

Pending implementation. Evidence: `docs/test/test401.md`.

## Boundaries and follow-up

This policy addition is source-level only. It does not establish full network
architecture coverage or hosted workload behavior. Route tables, NAT, gateways,
VPC endpoints, and hybrid connectivity remain separate coverage items. Keep the
PR draft until the product's customer-readiness gate is met.
