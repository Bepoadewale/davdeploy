# ticket162 — Add private HTTPS egress for the App Runner VPC connector

PR: Pending
Branch: `fix/customer-app-runner-private-egress`

## Problem / goal

The validated image and IAM roles succeeded, but App Runner failed after image pull with a zero-egress
VPC connector and no NAT route.

## Current repo state

The customer sandbox has two private subnets and a no-egress connector security group. The service
cannot complete runtime deployment despite a healthy local container startup.

## Research / references used

- App Runner deployment and CloudWatch service logs.
- ECR image manifest and local `/healthz` startup validation.

## Work planned for the PR

- Add a tagged Internet Gateway, one NAT gateway, private-route associations, and HTTPS-only
  connector egress.

## Acceptance criteria

- [ ] Workload instances remain in private subnets.
- [ ] Outbound workload traffic is restricted to TCP 443 through NAT.
- [ ] Terraform validation and CI pass.

## Acceptance status

Implementation and focused validation complete; CI pending.

## Tests / validation performed

- Focused cloud execution and customer connection tests.
- Terraform formatting and configuration validation using the pilot AWS profile.

## Evidence files produced

- `docs/test/test162.md`

## Boundaries

This adds required outbound runtime connectivity; it adds no inbound workload rule and no destroy path.

## Follow-up work

Deploy the foundation update, create a fresh approved service plan, verify healthy service state, and
then execute the customer-authorized governed destroy.
