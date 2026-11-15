# ticket412 — bounded Lambda and HTTP API plan pricing

PR: #412 https://github.com/Bepoadewale/davdeploy/pull/412
Branch: `feat/nova-lambda-api-pricing-412`

## Problem / goal

Generated plans containing Lambda or API Gateway HTTP API resources currently
fail closed as unpriced. Add trusted regional pricing for a narrow,
serverless API configuration using explicit, revision-bound monthly usage
ranges. Do not treat an unknown request volume, duration, data transfer amount,
or resource setting as zero.

## Current repo state

Backend `main` is `a9c5ca1` (PR #411). The pricing evaluator prices bounded
EBS, S3, SQS, and selected RDS MySQL resources. It rejects other material
resources. Exact-plan apply remains disabled and unwired in draft PR #399.

## Research / references used

- [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/)
- [Amazon API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/)
- [Amazon CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/)
- [AWS Price List GetProducts API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html)
- [AWS data transfer pricing](https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer)
- [Lambda configuration and memory](https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html)
- [Lambda architecture selection](https://docs.aws.amazon.com/lambda/latest/dg/foundation-arch.html)

## Work planned for the PR

- Add strict typed usage assumptions for monthly Lambda invocations and
  duration, internet egress, and CloudWatch log ingestion/storage, plus HTTP API
  request and outbound-data ranges, keyed to validated planned resource addresses.
- Persist assumptions with the trusted revision and bind them into generated
  pricing evidence, manifest digests, and approval eligibility.
- Price only on-demand Lambda x86_64/arm64 ZIP functions with bounded memory,
  default ephemeral storage, no VPC attachment, and a matching Standard CloudWatch
  log group with explicit retention, plus API Gateway v2 HTTP APIs. Reject VPC
  links, detailed stage metrics/logs, customer-managed log keys and unpriced resources.
- Use exact regional Price List matches, conservative tier rates, and explicit
  assumptions. Do not subtract Free Tier or account credits from approval
  estimates, including existing S3, SQS and RDS usage lines.
- Add negative tests for missing/stale assumptions, unknown settings,
  ambiguous prices, multiple functions/APIs, and digest changes.

## Acceptance criteria

- [x] Lambda request, duration, CloudWatch log ingestion, and log storage costs
      use exact regional catalog products for the planned architecture and memory.
- [x] HTTP API request and outbound transfer costs use exact regional rates.
- [x] Every usage assumption is validated, persisted, and bound to the exact
      revision and plan; changes invalidate stale approvals.
- [x] Unknown material resources or unsupported pricing settings remain
      explicitly unpriced and block approval.
- [ ] Focused tests, full verification, documentation checks, and required
      hosted CI pass. Local focused and full verification pass; hosted CI is pending.
- [x] No AWS workload is applied or claimed as certified.

## Acceptance status

Implemented and verified locally and in hosted CI. The draft remains open until the
final evidence commit has passing checks and the PR is reviewed. This pricing
package does not wire or enable the hosted apply path.

## Tests / validation performed

See `docs/test/test412.md` for focused and full verification, read-only AWS Price
List checks, and current limitations. Price fixtures are offline tests; they do
not represent an AWS bill.

## Evidence files produced

- `docs/tickets/ticket412.md`
- `docs/test/test412.md`

## Boundaries

This package will not enable apply, infer customer account discounts, apply
Free Tier credits, price WebSocket/REST APIs, Lambda provisioned concurrency,
VPC/NAT/private-link costs, non-Standard CloudWatch logs, customer-managed
CloudWatch encryption keys, or represent estimates as a billing cap.

## Follow-up work

Use the first hosted milestone to validate these assumptions with real API
behavior and observed usage. Expand other compute families only with explicit
regional rates and bounded usage models.

## Status ledger

- Status: locally and hosted CI verified; final evidence commit checks pending.
- Source: branch `feat/nova-lambda-api-pricing-412`, implementation commit `4252a88171c2478b00ce60ef424969dec5ac1952`, draft PR #412.
- Deployed version: none; no deployment or AWS workload mutation was performed.
- Current operation: push hosted evidence update, then run required checks on the final PR head.
- Next command: `gh pr checks 412 --watch --interval 120` after pushing the final evidence commit.
- Blockers: none known locally; do not enable apply from this PR.
