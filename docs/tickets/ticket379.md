# ticket379 — support bounded VPC metadata reads during Nova planning

PR: draft pending bootstrap
Branch: `feat/nova-network-plan-read-profile-379`

## Problem / goal

Nova's fixed customer plan-role profile does not include EC2 network metadata
reads. Terraform cannot safely plan a composed private application graph that
uses VPCs, subnets, routes, or security groups until the plan role can inspect
the required network metadata. Add only the fixed read-only EC2 API actions
needed by the supported network resource types, restricted to the trusted plan
region in each run. Do not add mutation actions or general EC2 read access.

## Current repo state

Backend `main` is `09bdb471a995d77f7eac95d9ca4d6f6899b95d04` after PR #378.
`nova_plan_access.py` rejects VPC, subnet, route, NAT, and security-group
resource types. Its session policy scopes existing supported service reads to
proposal-derived resource ARNs. EC2 Describe APIs do not support resource-level
permissions, so their session-policy boundary must use the AWS-supported
regional condition keys and an explicit deny for region mismatches.

## Research / references used

- AWS Service Authorization Reference, Amazon EC2:
  https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html
- Official HashiCorp AWS provider documentation for VPC, subnet, and security
  group resources:
  https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc
  https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet
  https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group

## Work planned for the PR

- Define the smallest verified fixed EC2 Describe action list needed for the
  initial private-network resource set.
- Add supported resource types and a region-bound session-policy statement;
  preserve explicit denies for writes and other services, including attempts
  to use the allowed network read actions outside the trusted region.
- Keep the customer role template and action contract synchronized.
- Add negative and positive tests for region scoping, proposal gating, and
  prohibited EC2 mutations.
- Record exact local verification and limitations; keep role deployment and
  hosted execution gates disabled.

## Acceptance criteria

- [ ] Only verified EC2 metadata-read actions are enabled; no EC2 mutations,
      wildcard service patterns, or general `Describe*` permission are added.
- [ ] Session access is granted only for supported network proposals and the
      trusted region, with an explicit deny outside it.
- [ ] Existing S3, RDS, IAM, Lambda, API Gateway, DynamoDB, and SQS scope tests
      remain passing and policy size stays within AWS limits.
- [ ] Focused tests, `make verify`, Terraform validation, documentation
      conventions, and clean-room proof pass.
- [ ] All limitations and the fact that no AWS/customer role was changed are
      documented; required final-head CI and review pass.

## Acceptance status

- [ ] Implementation and validation complete.

## Tests / validation performed

- Bootstrap only; implementation validation will be added before review-ready.

## Evidence files produced

- `docs/tickets/ticket379.md`
- `docs/test/test379.md` (required for this executable/IAM-profile change)

## Boundaries

- This changes source policy construction only. It does not deploy the plan
  role, enable hosted planning, create customer resources, or permit EC2
  mutations.
- EC2 Describe calls without resource-level authorization can expose regional
  network metadata; the ticket must document the exact action and condition
  boundary that the implementation enforces.

## Follow-up work

- Install and verify the customer plan-only role, prove effective permissions,
  and run the isolated hosted saved-plan flow only after the separate state,
  pricing, and approval dependencies are met.
