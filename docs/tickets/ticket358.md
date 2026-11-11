# ticket358 — review open API Gateway routes in Nova plans

PR: [#358](https://github.com/Bepoadewale/davdeploy/pull/358) (draft; number reserved)
Branch: `security/apigateway-route-auth-policy-358`
Base: `main`

## Problem / goal

The actual generated-plan policy does not inspect `aws_apigatewayv2_route`
authorization. API Gateway defines `NONE` as open access, and the Terraform
provider defaults an omitted authorization type to `NONE`. Require explicit
human review for open routes and deny routes whose authorization cannot be
verified.

## Current repo state

- Backend `main` is `11e66e878933a69638128a8bab80115c051d230a` (PR #356).
- Actual-plan policy covers selected IAM, S3, SQS, Lambda, network, database,
  and EBS risks but not API Gateway route authorization.
- Nova customer planning/apply remain disabled; this change does not enable
  execution or alter existing customer resources.

## Research / references used

- [Amazon API Gateway Route API](https://docs.aws.amazon.com/apigatewayv2/latest/api-reference/apis-apiid-routes-routeid.html): `NONE` is open access; HTTP API options include `JWT`, `AWS_IAM`, and `CUSTOM`.
- [Terraform AWS provider `aws_apigatewayv2_route`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/apigatewayv2_route): `authorization_type` is optional and defaults to `NONE`.

## Work planned for the PR

- Treat unknown/missing route authorization as policy-critical and deny it.
- Add actual-plan findings for open `NONE` routes and allowlisted authenticated
  authorization types, without exposing raw route values.
- Add focused tests and update policy version/status evidence.

## Acceptance criteria

- [x] Missing, unknown, malformed, and unsupported authorization values deny.
- [x] Explicit `NONE` yields an open-route review finding; `JWT`, `AWS_IAM`,
  and `CUSTOM` do not yield that finding.
- [x] Focused tests, full verification, and clean-room local proof pass;
  documentation conventions and required hosted CI remain pending.
- [x] No customer AWS plan or infrastructure mutation was performed.

## Acceptance status

The policy check and focused tests are implemented. The complete policy still
denies these untaggable route resources at the ownership boundary until exact
ownership records for non-taggable resources are implemented. Hosted planning
remains disabled; no customer AWS plan or infrastructure mutation occurred.

## Tests / validation performed

- `uv run pytest tests/test_generated_plan_policy.py -q` — 111 passed.
- `uv run ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py` — passed.
- `make local-proof` — passed with 962 tests, API contract, customer-plan E2E,
  seed, trace, Compose validation and full verification (one existing
  Starlette/httpx deprecation warning).

## Evidence files produced

- This ticket tracks the scope and verification for PR #358.

## Boundaries

This is a bounded actual-plan policy change. It does not claim complete API
Gateway policy coverage, solve ownership for non-taggable resources, or enable
the customer executor. Route ownership remains fail-closed until a separate
trusted ownership-record path exists.

## Follow-up work

Continue with other actual-plan policy gaps, then finish the gated hosted
plan-only path, trusted cost evidence, and customer execution lifecycle.
