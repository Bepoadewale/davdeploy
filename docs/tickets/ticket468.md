# ticket468

PR: [#468 — feat: enforce safe ACM certificate plan settings](https://github.com/Bepoadewale/davdeploy/pull/468) (draft)

Branch: `feat/acm-certificate-plan-safety-468`

## Problem / goal

The ACM certificate module requests DNS validation but leaves the key algorithm
and export setting implicit. Generated-plan policy does not validate these
request settings or fail closed when they are unknown. Make the supported
request shape explicit and deny exportable or otherwise unsupported plans.

## Current repo state

- `infrastructure/terraform/modules/acm-certificate/main.tf` requests DNS
  validation and outputs the domain validation options.
- The module did not explicitly set key algorithm or certificate export
  behavior.
- Generated-plan policy had no ACM-specific checks.
- `test254` records ACM/SES DNS validation; no evidence proves domain ownership
  or this module's full issue/renewal/DNS lifecycle.
- No ACM or DNS resource mutation is part of this PR.

## Research / references used

- [Terraform AWS provider `aws_acm_certificate` resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/acm_certificate.html)
- [AWS ACM best practices and DNS validation](https://docs.aws.amazon.com/acm/latest/userguide/acm-bestpractices.html)
- [AWS ACM certificate types and export behavior](https://docs.aws.amazon.com/acm/latest/userguide/certificate-types.html)
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/acm-certificate/main.tf`
- `tests/test_generated_plan_policy.py`

## Work planned for the PR

1. Mark certificate domain, validation method, key algorithm, and export
   behavior as policy-critical known values.
2. Require DNS validation, RSA_2048, and disabled export for the checked-in
   module shape.
3. Add accepted, unsafe, and unknown-value regression tests.
4. Update the capability matrix while leaving domain ownership, DNS
   publication, issuance, renewal, and full lifecycle evidence open.

## Acceptance criteria

- [x] The module explicitly requests RSA_2048 and disabled export.
- [x] Generated-plan policy accepts the module shape and rejects unsupported
  validation, algorithm, export, and unknown values.
- [x] Regression tests cover supported, unsafe, and unknown settings.
- [x] The evidence matrix keeps domain ownership and complete ACM lifecycle
  unproven.
- [x] No AWS or hosted control-plane resources are changed.
- [x] Focused and full policy tests, formatting, Terraform validation,
  documentation conventions, and `git diff --check` pass.
- [x] Final-head CI and review/merge state are tracked on PR #468; merge only
  after all required checks pass.

## Acceptance status

Implementation is complete on PR #468. The plan checks do not prove domain
ownership, certificate issuance, DNS publication, or renewal.

## Tests / validation performed

- `tests/test_generated_plan_policy.py` — 389 passed.
- Ruff on changed Python files — passed.
- Terraform format and module validation — passed.
- `GITHUB_PR_NUMBER=468 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Final-head CI is tracked on PR #468.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/acm-certificate/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket468.md`

## Boundaries

- Source and documentation only; do not request ACM certificates or modify DNS
  for this package.
- Do not access or change hosted control-plane resources.
- Do not claim domain ownership, certificate validity/renewal, DNS publication,
  production TLS behavior, or full cost/lifecycle coverage.
- Preserve `--only-show-errors`, `.venv-pr399/`,
  `docs/test/fixtures/nova-batch-retry-458/terraform.tfstate`, and all
  generated provider lock files.

## Follow-up work

Add separately authorized customer-side certificate issuance, DNS validation,
attachment, HTTPS health, renewal, teardown, and independent absence evidence.
