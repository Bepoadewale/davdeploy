# ticket432 — require HTTPS for CloudFront viewers

PR: https://github.com/Bepoadewale/davdeploy/pull/432
Branch: `feat/cloudfront-viewer-https-policy-432`

## Problem / goal

The shared generated-plan policy does not inspect CloudFront viewer protocol
settings. A distribution can therefore allow cleartext HTTP even when its
origins and other resources are policy-checked. Require each default and
ordered cache behavior to either redirect viewers to HTTPS or accept HTTPS
only. Missing, unknown, malformed, and cleartext-permitting values must fail
closed.

## Current repo state

Backend `main` is `87c4b25d9aa57d6ce26aa921884dcfbf5210abf5`; hosted runtime
remains PR #420 commit `9951caa9244128b1551fea3af66b1bdbf884c800`. PR #399 is
open/draft, source-only and execution-gated off, at
`7d657d2cbb6b312b2f473ddcc6745423d237219b`; fresh CI run `44208035004` is
pending. No Nova customer workload has been applied or certified.

## Research / references used

- AWS CloudFront Developer Guide, [Require HTTPS for communication between
  viewers and CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-https-viewers-to-cloudfront.html).
- AWS CloudFront API, [CacheBehavior](https://docs.aws.amazon.com/cloudfront/latest/APIReference/API_CacheBehavior.html).
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

AWS documents the viewer policy values `allow-all`, `redirect-to-https`, and
`https-only`; only the latter two require TLS for viewer access. Redirects can
add a second request and are not identical to HTTPS-only behavior. This policy
checks viewer-to-CloudFront protocol only; it does not prove origin-side TLS,
WAF/cache safety, pricing, or workload health.

## Work planned for the PR

- Add safety-critical unknown paths for viewer protocol policies on default
  and ordered behaviors.
- Deny a distribution when any cache behavior is absent, malformed, unknown,
  or permits cleartext HTTP.
- Accept `redirect-to-https` and `https-only` for every configured behavior.
- Add negative and positive policy tests and update the matrix's CloudFront row
  with this limited source-level rule.

## Acceptance criteria

- [ ] `allow-all`, missing, malformed, or unknown viewer policy is denied.
- [ ] Every default and ordered cache behavior is inspected.
- [ ] `redirect-to-https` and `https-only` remain accepted.
- [ ] Findings contain no plan values or sensitive content.
- [ ] Focused policy tests, full verification, docs conventions, and diff checks
  pass.
- [ ] All seven required CI checks pass on the implementation commit.

## Acceptance status

Implementation has not started. This is a source policy change only. No AWS
distribution, Terraform plan/apply, hosted runtime, or customer workload will
be changed.

## Tests / validation performed

No checks have run for this implementation yet. No `docs/test/test432.md` is
required because no customer workload is part of this package.

## Evidence files produced

- `docs/tickets/ticket432.md`
- Updated CloudFront policy tests and capability matrix
- No `docs/test/test432.md` is required because no customer workload was run.

## Boundaries

Source-only plan-policy work. Do not deploy the control plane, alter CloudFront
or DNS, issue credentials, or apply customer infrastructure.

## Follow-up work

CloudFront origin TLS, response headers, WAF/cache behavior, price evidence, and
Nova-hosted customer lifecycle remain separate acceptance work. Keep PR #399
draft with apply and credential gates disabled.
