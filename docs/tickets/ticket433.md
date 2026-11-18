# ticket433 — require HTTPS for CloudFront origins

PR: https://github.com/Bepoadewale/davdeploy/pull/433
Branch: `feat/cloudfront-origin-tls-policy-433`

## Problem / goal

The shared generated-plan policy now requires HTTPS from viewers to CloudFront,
but a custom origin can still receive requests over cleartext HTTP or negotiate
legacy TLS. Require each planned custom origin to use HTTPS and TLS 1.2. Allow
`match-viewer` only with viewer behaviors already constrained to HTTPS by the
CloudFront viewer rule. Keep missing, malformed, unknown, or incomplete origin
settings fail-closed.

## Research / references used

- AWS CloudFront Developer Guide, [Require HTTPS for communication between
  CloudFront and your custom origin](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-https-cloudfront-to-custom-origin.html).
- AWS CloudFront Developer Guide, [Origin settings](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html).
- AWS CloudFront API, [CustomOriginConfig](https://docs.aws.amazon.com/cloudfront/latest/APIReference/API_CustomOriginConfig.html).
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

AWS documents `http-only`, `match-viewer`, and `https-only` origin policies;
`match-viewer` is appropriate only when the viewer policy redirects to HTTPS or
requires HTTPS. The custom-origin SSL protocol list includes TLS 1.2 and older
protocols. S3 website endpoints cannot use HTTPS and are represented as custom
origins, so this policy will reject them through their cleartext protocol
setting. Standard S3 origins use the already-enforced viewer HTTPS policy.

## Current repo state

Backend `main` is `5de5aff56159fa2968a8dcd3c31557cb955b0068` (PR #432,
source-only viewer HTTPS policy). Hosted runtime remains PR #420 commit
`9951caa9244128b1551fea3af66b1bdbf884c800`. PR #399 is open/draft and
execution-gated off at `135176e1c5c4a55e8fff7c93c67278ba6a4655a6`; all seven
checks passed in run `44211520776`. No Nova customer workload has been applied
or certified.

## Work planned for the PR

- Add unknown-value coverage for custom-origin protocol and TLS settings.
- Inspect every configured CloudFront origin and deny missing or malformed
  origin structures.
- Require custom origins to use `https-only` or `match-viewer`, with the latter
  relying on the existing viewer HTTPS rule for the same distribution.
- Require a TLS 1.2-only origin protocol list; deny cleartext, legacy TLS, and
  unknown values without echoing plan content.
- Add positive and negative policy tests and update the capability matrix with
  the source-only scope and remaining cache, response-header, and access gaps.

## Acceptance criteria

- [x] Every custom origin is inspected; malformed or absent origin settings
  fail closed.
- [x] `https-only` plus TLS 1.2 is eligible for human review.
- [x] `match-viewer` is accepted only alongside CloudFront viewer policies that
  require HTTPS.
- [x] `http-only`, legacy TLS, missing TLS settings, and unknown values are
  denied.
- [x] Findings do not expose plan values or sensitive content.
- [x] Focused tests, full verification, documentation conventions, and diff
  checks pass.
- [ ] All seven required PR checks pass on the final PR head.

## Acceptance status

Implementation and local validation are complete. Final-head GitHub checks are
pending.

## Tests / validation performed

Focused `tests/test_generated_plan_policy.py`: 207 passed. Full verification
with `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`:
1,331 passed; Ruff, Actions configuration, OpenAPI, and Compose checks passed.
Documentation conventions, `git diff --check`, and
`terraform fmt -check -recursive` passed. The only output warning is the
existing Starlette/httpx deprecation.

## Evidence files produced

- `docs/tickets/ticket433.md`
- CloudFront origin policy implementation and generated-plan tests
- Updated CloudFront rows in `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Boundaries

Source-only generated-plan policy work. Do not deploy the control plane, alter
CloudFront or DNS, issue credentials, run Terraform against AWS, or apply
customer infrastructure. No customer workload is part of this package.

## Follow-up work

Response headers, cache safety, private S3 origin access, origin health,
pricing, and Nova-hosted customer lifecycle remain separate evidence gaps.
