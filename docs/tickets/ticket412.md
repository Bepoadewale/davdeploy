# ticket412 — bounded Lambda and HTTP API plan pricing

PR: draft to be opened
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
- [AWS Price List API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html)
- [Lambda configuration and memory](https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html)
- [Lambda architecture selection](https://docs.aws.amazon.com/lambda/latest/dg/foundation-arch.html)

## Work planned for the PR

- Add strict typed usage assumptions for monthly Lambda invocations and
  duration, plus HTTP API request and outbound-data ranges, keyed to validated
  planned resource addresses.
- Persist assumptions with the trusted revision and bind them into generated
  pricing evidence, manifest digests, and approval eligibility.
- Price only on-demand Lambda x86_64/arm64 functions with bounded memory and
  supported ephemeral storage, and API Gateway v2 HTTP APIs without caching or
  VPC links. Reject unsupported configurations and material unpriced resources.
- Use exact regional Price List matches, conservative tier rates, and explicit
  assumptions. Do not subtract Free Tier or account credits from approval
  estimates.
- Add negative tests for missing/stale assumptions, unknown settings,
  ambiguous prices, multiple functions/APIs, and digest changes.

## Acceptance criteria

- [ ] Lambda request and duration costs use exact regional catalog products
      for the planned architecture and memory.
- [ ] HTTP API request and outbound transfer costs use exact regional rates.
- [ ] Every usage assumption is validated, persisted, and bound to the exact
      revision and plan; changes invalidate stale approvals.
- [ ] Unknown material resources or unsupported pricing settings remain
      explicitly unpriced and block approval.
- [ ] Focused tests, full verification, documentation checks, and required
      hosted CI pass.
- [ ] No AWS workload is applied or claimed as certified.

## Acceptance status

Not started. This initial commit creates the technical ticket so a draft PR can
be opened before implementation.

## Tests / validation performed

This bootstrap commit changes documentation only, so it needs no runtime test
evidence. The runnable implementation will add `docs/test/test412.md` and
record exact commands, hosted CI, and limitations. Pricing fixtures will be
labelled offline tests; they do not represent an AWS bill.

## Evidence files produced

- `docs/tickets/ticket412.md`

## Boundaries

This package will not enable apply, infer customer account discounts, apply
Free Tier credits, price WebSocket/REST APIs, Lambda provisioned concurrency,
VPC/NAT/private-link costs, or represent estimates as a billing cap.

## Follow-up work

Use the first hosted milestone to validate these assumptions with real API
behavior and observed usage. Expand other compute families only with explicit
regional rates and bounded usage models.
