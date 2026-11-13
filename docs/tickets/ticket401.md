# ticket401 — inspect network ACL exposure in generated Terraform plans

PR: https://github.com/Bepoadewale/davdeploy/pull/401 (open draft)
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

## Work planned for the PR

- Inspect actual plan values and unknown metadata for `aws_network_acl`,
  `aws_default_network_acl`, and
  `aws_network_acl_rule` ingress rules.
- Deny malformed, incomplete, or policy-critical unknown ACL entries.
- Deny public inbound rules for configured administrative/data ports; require
  human review for public web/general ingress, including IPv4 and IPv6 sources.
- Recognize globally routable IPv4/IPv6 source ranges in ACL and security-group
  policy, rather than checking only `/0`.
- Add negative and valid scoped-network regression cases. No cloud mutation or
  feature-gate change.

## Acceptance criteria

- [x] Actual plans with malformed or critical unknown ACL ingress are denied.
- [x] Public administrative/data ports are denied for IPv4 and IPv6 CIDRs.
- [x] Public web/general ingress requires review; private/scoped ingress is not
      misclassified as public.
- [x] Focused tests, full verification, docs convention, and diff checks pass.
- [x] Required hosted CI passed on implementation commit `481c386` in run
      `43498568620`; this evidence-only update is subject to its own CI run.
- [x] No apply, deployment, or AWS resource mutation occurs.

## Acceptance status

Locally implemented and verified. Hosted PR checks are pending at this draft
revision. No deployment or customer workload is claimed.

## Tests / validation performed

Focused plan-policy tests, full `make verify`, the isolated `make local-proof`,
documentation conventions, and diff checks are recorded in
`docs/test/test401.md`.

## Evidence files produced

- `docs/test/test401.md`
- Updated `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Boundaries

This policy addition is source-level only. It does not establish full network
architecture coverage or hosted workload behavior. ACL-to-subnet associations,
route tables, NAT, gateways, VPC endpoints, egress policy, and hybrid
connectivity remain separate coverage items. Public ACL rules are evaluated
individually; rule-number precedence and reachability through the full VPC
topology are not computed. Keep the PR draft until the product's
customer-readiness gate is met.

## Follow-up work

Add network ACL association and rule-precedence analysis, then continue with
route, egress, endpoint, and end-to-end reachability policy coverage.
