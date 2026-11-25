# ticket502 — Price bounded VPC and NAT Gateway plans

## Goal

Add conservative, region-specific generated-plan pricing for the VPC and NAT
Gateway shapes admitted by the source policy. Include hourly NAT Gateway
charges, data processing, public IPv4 addresses, internet egress, and any
cross-Availability-Zone transfer cost that the plan and trusted assumptions can
bound. A one-rate NAT estimate must never be reported as a complete network
estimate.

## Current repository state

- Source `main` is `e7b697127691f8454e1f468a562338e6276957b4` (PR #501).
- PR #500 adds source-only checks for a bounded VPC topology, including
  same-plan Internet Gateway, NAT Gateway, Elastic IP, subnets, and route
  associations. Its public/private routing shape makes network costs relevant
  to plan approval.
- `apps/api/src/davdeploy/generated_plan_pricing.py` prices selected storage,
  database, queue, serverless, log, and internet-egress usage. Unpriced managed
  resources fail closed. Pricing evidence has integrity-bound usage context
  and a versioned manifest.
- No AWS resources, remote state, hosted control-plane state, or runtime are
  part of this source-only change.

## Research and references

- [AWS NAT Gateway pricing guide](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-pricing.html): NAT Gateways incur hourly and per-GB processing charges; cross-AZ placement and traffic can add transfer cost.
- [Amazon VPC pricing](https://aws.amazon.com/vpc/pricing/): regional NAT pricing, public IPv4 hourly charges, and transfer pricing are distinct cost components.
- [AWS Price List API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html): current regional prices must come from trusted AWS price data, not customer-supplied rates.

## Work to be done

1. Define strict, bounded, persisted monthly usage assumptions for each exact
   planned NAT address and its related public IPv4/transfer quantities.
2. Retrieve exact regional NAT hourly and processing rates, plus required
   public IPv4 and transfer rates, through the existing trusted AWS Price List
   adapter. Preserve catalog SKU, digest, effective time, and source evidence.
3. Bind assumptions to the integrity-checked customer revision and pricing
   manifest. Keep saved v2–v7 pricing evidence readable.
4. Price only the admitted same-plan network shape. Fail closed for unknown
   quantities, unsupported gateways, unmodeled endpoints/attachments, missing
   rates, and material transfer costs without assumptions.
5. Add regression tests and update the capability matrix and this ticket with
   precise limits. Keep all work on this PR branch.

## Acceptance criteria

- [ ] A clean, supported VPC/NAT plan with complete trusted assumptions gets
  regional monthly low/high evidence for NAT hours, processing, public IPv4,
  egress, and applicable cross-AZ transfer.
- [ ] A NAT plan missing any material usage or rate remains incomplete or
  unavailable and cannot pass pricing approval.
- [ ] No customer-provided unit price can influence the result.
- [ ] NAT public IPv4 cost is counted once when an Elastic IP is bound to that
  NAT; unrelated public addresses are either separately priced or block the
  complete estimate.
- [ ] NAT counts and usage assumptions are bound to exact plan addresses and
  persisted revision context; malformed, excessive, or mismatched assumptions
  fail closed.
- [ ] Existing pricing manifests remain readable and manifest/evidence digests
  cover new assumptions and price lines.
- [ ] Regression tests cover supported regional catalog products, cost
  arithmetic, missing/ambiguous prices, missing/invalid assumptions, cross-AZ
  transfer, duplicate IPv4 accounting, and unsupported network shapes.
- [ ] The VPC/NAT capability matrix describes exactly what is priced and what
  remains blocked.
- [ ] No hosted runtime, control-plane, Terraform state, or AWS resource is
  changed; no deployment is claimed.

## Acceptance status

- [ ] Implementation complete.
- [ ] Focused validation complete.
- [ ] Required GitHub checks passed on the final PR head.
- [ ] PR reviewed and merged.

## Validation and evidence

Record exact focused test, lint, type-check, and documentation commands here.
This PR is source-only and must not create a `docs/test/test502.md` AWS workload
report.

## Boundaries

Preserve PR-only workflow. Never push directly to `main`. Do not touch AWS,
hosted control-plane state/locks/runtime, or external resources. Keep existing
protected untracked files and unrelated worktrees untouched. Do not claim that
Nova customer execution or a complete customer bill has been certified.

## Follow-up

Any VPC transfer, endpoint, peering, Transit Gateway, VPN, load balancer,
firewall, or other material network cost not proven by this package remains
unpriced and blocks approval until separately modeled.
