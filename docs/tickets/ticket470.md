# ticket470

PR: [#470 — feat: enforce safe Route 53 zone plan settings](https://github.com/Bepoadewale/davdeploy/pull/470) (draft)

Branch: `feat/route53-zone-plan-safety-470`

## Problem / goal

The Route 53 zone module leaves the record-destruction behavior implicit and
the generated-plan policy has no zone-specific checks. Explicitly preserve
records during zone deletion and reject plans that cannot show the zone name,
public-zone shape, or safe deletion setting.

## Current repo state

- `infrastructure/terraform/modules/dns-zone/main.tf` creates a hosted zone
  from a caller-provided name.
- Route 53 determines public/private zone behavior through VPC association
  configuration; this module has no VPC association block.
- `force_destroy` controls whether records can be removed with the zone; the
  module previously relied on the provider default.
- Existing `test260` records public DNS failover and `test244` has related
  resource evidence, but ownership/delegation and this module's full customer
  lifecycle remain open.
- No hosted zone or DNS record is created by this PR.

## Research / references used

- [Terraform AWS provider `aws_route53_zone` resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route53_zone.html)
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/dns-zone/main.tf`
- `tests/test_generated_plan_policy.py`

## Work planned for the PR

1. Mark zone name, VPC associations, and `force_destroy` as policy-critical
   known values.
2. Permit only the module's public-zone form with no VPC associations and
   require `force_destroy = false`.
3. Add passing, unsafe, and unknown-value regression tests.
4. Update the capability matrix and leave ownership, delegation, record,
   failover, lifecycle, and pricing evidence open.

## Acceptance criteria

- [x] The module explicitly sets `force_destroy = false` and omits private VPC
  associations.
- [x] Generated-plan policy accepts the intended zone shape and denies
  private-zone associations, empty names, destructive deletion, and unknown
  critical values.
- [x] Regression tests cover supported, unsafe, and unknown settings.
- [x] The capability matrix keeps complete DNS support and ownership evidence
  open.
- [x] No AWS or hosted control-plane resources are changed.
- [x] Focused and full policy tests, Terraform validation, documentation
  conventions, and `git diff --check` pass.
- [x] Final-head CI and review/merge state are tracked on PR #470; merge only
  after all required checks pass.

## Acceptance status

Implementation is complete on PR #470. These checks do not prove domain
ownership, record correctness, delegation, DNS failover, or complete pricing.

## Tests / validation performed

- `tests/test_generated_plan_policy.py` — 396 passed.
- Ruff on changed Python files — passed.
- Terraform format and module validation — passed.
- `GITHUB_PR_NUMBER=470 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Final-head CI is tracked on PR #470.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/dns-zone/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket470.md`

## Boundaries

- Source and documentation only; do not create or delete AWS hosted zones or
  DNS records for this package.
- Do not access or change hosted control-plane resources.
- Do not claim DNS ownership, records, delegation, failover, customer
  lifecycle, or complete DNS cost support from generated-plan checks.
- Preserve `--only-show-errors`, `.venv-pr399/`,
  `docs/test/fixtures/nova-batch-retry-458/terraform.tfstate`, and generated
  provider lock files.

## Follow-up work

Add separately authorized customer-side DNS lifecycle evidence for record
create/update/failover/recovery and teardown, with independent absence checks.
