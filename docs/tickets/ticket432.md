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
green on all seven checks. No Nova customer workload has been applied or
certified.

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

- [x] `allow-all`, missing, malformed, or unknown viewer policy is denied.
- [x] Every default and ordered cache behavior is inspected.
- [x] `redirect-to-https` and `https-only` remain accepted.
- [x] Findings contain no plan values or sensitive content.
- [x] Focused policy tests, full verification, docs conventions, and diff checks
  pass.
- [x] All seven required CI checks pass on implementation commit
  `f73835de1ece9a482003fa00814fdbf31cd05b45` in run `44208891956`.

## Acceptance status

Implementation is complete and verified. All seven required checks passed on
implementation commit `f73835de1ece9a482003fa00814fdbf31cd05b45` in run
`44208891956`; all seven checks also passed on final PR head
`cb8d5dcc40261f0a85cd62586ef249754a39fa04` in run `44209578884`. This is a
source policy change only; no AWS distribution, Terraform plan/apply, hosted
runtime, or customer workload was changed.

## Tests / validation performed

- Focused `tests/test_generated_plan_policy.py`: 190 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`:
  1,314 passed; Ruff, Actions configuration, OpenAPI, and Compose checks passed.
- `GITHUB_PR_NUMBER=432 .venv-pr399/bin/python scripts/check_doc_conventions.py`:
  passed.
- `git diff --check`: passed.
- Final-head GitHub CI run `44208891956` passed all seven checks on
  `f73835de1ece9a482003fa00814fdbf31cd05b45`; final PR-head CI run
  `44209578884` passed all seven checks on
  `cb8d5dcc40261f0a85cd62586ef249754a39fa04` after the ticket update.
- No `docs/test/test432.md` is required because no customer workload was part of
  this package.

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
