# ticket500 — bind generated VPC topology and egress plans

PR: [#500 — feat: bind generated VPC topology and egress plans](https://github.com/Bepoadewale/davdeploy/pull/500)
Branch: `feat/vpc-route-policy-500`

## Problem / goal

Generated-plan review currently checks some security-group and network-ACL ingress, but it does not establish a VPC's subnet topology, route-table associations, internet gateway, NAT gateway, or default egress paths. This can leave public exposure, private-subnet egress, and cost-driving NAT resources unreviewed.

Add deterministic checks for the repository's bounded `modules/vpc` topology. Unsupported or ambiguous shapes must fail closed or require review. This is source-only; no Terraform plan, apply, AWS resource change, hosted control-plane access, or remote-state operation is in scope.

## Current repo state

- Current `main` is `e4285be326956278e1cc6919c03020b36383e4d6` (PR #499).
- `infrastructure/terraform/modules/vpc/main.tf` defines one VPC, indexed public/private subnet sets, an internet gateway, one public and one private route table, subnet associations, and one EIP/NAT gateway. Private subnets route default egress through NAT; public subnets route default egress through the IGW. Both subnet types disable automatic public IPv4 assignment.
- `apps/api/src/davdeploy/generated_plan_policy.py` has generic SG/ACL ingress checks but no VPC topology/egress checker.
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` records complete VPC route/NAT/topology policy as a gap.
- The Terraform run monitor currently reports zero active operations. AWS identity is account `654654474502`; this PR will not call AWS APIs.

## Research / references used

- Repository VPC module: `infrastructure/terraform/modules/vpc/main.tf`.
- Generated plan policy and tests: `apps/api/src/davdeploy/generated_plan_policy.py`, `tests/test_generated_plan_policy.py`.
- AWS [VPC route tables](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Route_Tables.html) and [NAT gateways](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html) describe subnet route associations and NAT egress.
- HashiCorp AWS provider plan schemas for VPC, subnet, route table, route table association, EIP, NAT gateway, and route resources.

## Work planned for the PR

1. Add a plan-shape checker for exactly one VPC, one IGW, one public/private route table, one bounded NAT/EIP pair, and bounded same-plan public/private subnet sets with complete associations.
2. Bind resource references to exact same-plan VPC, subnet, route-table, IGW, NAT, and EIP addresses; reject missing, duplicate, extra, mismatched, or unprovable route associations.
3. Require known private RFC1918 IPv4 CIDRs with valid containment/non-overlap, DNS support and hostnames, no automatic public IPv4 assignment, exact `0.0.0.0/0` public-to-IGW and private-to-NAT routes, and a NAT gateway in an associated public subnet.
4. Reject additional default, IPv6, peering, transit, or unreviewed route paths for this supported shape. Surface NAT presence and its cost as a human-review finding; do not claim complete network reachability or pricing.
5. Add accepted/rejected, reference-binding, and unknown-value regression coverage; bump policy version and reconcile the Nova capability matrix.
6. Run focused local validation and required CI; make no AWS or hosted control-plane change.

## Acceptance criteria

- [x] Exactly one supported VPC topology is recognized, with bounded public/private subnet sets, correct same-plan relationships, and no unreviewed extras.
- [x] Route associations prove each subnet's public/private classification and bind default routes to the correct same-plan IGW/NAT.
- [x] Invalid/overlapping/out-of-VPC CIDRs, unknown critical values, public IP auto-assignment, missing associations, extra routes, and mismatched resource references fail closed.
- [x] Findings are value-safe and explicitly require human review for NAT cost/egress implications.
- [ ] Focused regressions, docs conventions, diff checks, and final-head required GitHub CI pass; local checks pass, final CI remains pending.
- [x] Matrix distinguishes source policy from direct lifecycle evidence and does not claim Nova dispatch or customer certification.
- [x] No Terraform execution, AWS mutation, hosted-control-plane or remote-state change occurred.

## Acceptance status

The source policy, regression coverage, and matrix update are implemented. Local checks and all seven checks on the implementation commit pass. Final-head GitHub CI after this evidence update remains pending.

## Tests / validation performed

- `PYTHONDONTWRITEBYTECODE=1 /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest -p no:cacheprovider tests/test_generated_plan_policy.py -q` — 550 passed.
- `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py` — passed.
- `GITHUB_PR_NUMBER=500 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- All seven required checks passed on implementation commit `1de472f1ec819a8a42bcc49f4da0d01f6659d11f` in [CI run 45551603389](https://github.com/Bepoadewale/davdeploy/actions/runs/45551603389). Final-head CI after this ticket evidence update remains required.
- No Terraform plan/apply/destroy or AWS API operation was run.


## Evidence files produced

- `docs/tickets/ticket500.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- No customer workload evidence is planned because the PR changes generated-plan policy only.

## Boundaries

Keep network topology validation limited to the explicit supported module shape. VPNs, IPv6, peering/transit, VPC endpoints, DNS resolution/reachability, network ACL rule precedence, effective security-group reachability, cross-region paths, and full egress pricing remain unsupported until separately analyzed.

## Follow-up work

Direct module lifecycle evidence, complete NAT/egress pricing, and broader network reachability analysis remain separate gates. This PR does not prove Nova dispatch or customer certification.
