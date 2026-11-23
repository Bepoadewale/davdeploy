# ticket465

PR: [#465 — feat: enforce safe SSM parameter plan settings](https://github.com/Bepoadewale/davdeploy/pull/465) (draft)

Branch: `feat/ssm-parameter-plan-safety-465`

## Problem / goal

The `aws-parameter-config` module uses `SecureString` but leaves the
Parameter Store tier implicit. The generated-plan policy does not verify the
parameter encryption type, tier, or optional KMS key reference. Require an
explicit low-cost supported tier and fail closed on unsafe or unknown
encryption settings.

## Current repo state

- `infrastructure/terraform/modules/parameter-config/main.tf` creates one
  `aws_ssm_parameter` with `type = "SecureString"` and an optional KMS key.
- The module does not currently declare a tier. AWS may use the account and
  Region default tier when the resource omits one.
- AWS documents Standard tier as having no additional storage charge; Advanced
  tier incurs charges and cannot be downgraded in place.
- Terraform's provider documentation warns that the unencrypted SecureString
  value is stored in raw Terraform state. The existing `value` argument is
  marked sensitive for CLI display, but that does not encrypt it in state.
- No root-specific AWS lifecycle or runtime retrieval evidence exists.

## Research / references used

- [Terraform AWS provider `aws_ssm_parameter` resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_parameter.html)
- [AWS Parameter Store tier comparison](https://docs.aws.amazon.com/systems-manager/latest/userguide/parameter-store-advanced-parameters.html)
- [AWS Parameter Store overview and pricing comparison](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/parameter-config/main.tf`
- `tests/test_generated_plan_policy.py`

## Work planned for the PR

1. Mark parameter type, tier, and optional KMS key identity as critical known
   plan values.
2. Require `SecureString` and `Standard`; accept no custom KMS key or a known
   non-empty key reference.
3. Explicitly configure Standard tier in the checked-in module.
4. Add passing, unsafe-value, and unknown-value regression cases.
5. Update the capability matrix with the source checks and retain gaps around
   state confidentiality, access, rotation, runtime use, and lifecycle.

## Acceptance criteria

- [x] The module explicitly requests Standard tier.
- [x] Generated-plan policy permits `SecureString` + Standard and denies other
  types/tiers and malformed KMS key references.
- [x] Unknown type, tier, or KMS key references are denied.
- [x] Regression tests cover passing, unsafe, and unknown settings.
- [x] The evidence matrix describes source-only checks and keeps secret-state,
  runtime access, rotation, and lifecycle support open.
- [x] No AWS parameter or secret value is created or changed; no hosted
  control-plane resource is accessed or changed.
- [x] Focused and full policy tests, formatting, Terraform validation,
  documentation conventions, and `git diff --check` pass.
- [x] CI and merge state are tracked on PR #465; this package makes no
  deployment claim.

## Acceptance status

Implementation is in progress on PR #465. This is a generated-plan and module
baseline only. It does not make Terraform state safe for secret values or
establish parameter runtime or lifecycle support.

## Tests / validation performed

- `tests/test_generated_plan_policy.py` — 367 passed.
- Ruff on changed Python files — passed.
- `terraform fmt -check` and `terraform validate` — passed.
- `GITHUB_PR_NUMBER=465 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- CI run 45270676350 passed all seven checks on the implementation commit;
  see PR #465 for the latest head's required check results.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/parameter-config/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket465.md`

## Boundaries

- Code and documentation only; do not create, update, or delete AWS parameters
  or secrets for this package.
- Do not access or mutate hosted control-plane resources.
- Never put real secret values into tests, terminal output, generated evidence,
  plans committed to the repository, or documentation.
- Do not claim Terraform-state confidentiality, customer secret retrieval,
  rotation, revocation, or customer-managed KMS lifecycle support.
- Preserve `--only-show-errors`, `.venv-pr399/`,
  `docs/test/fixtures/nova-batch-retry-458/terraform.tfstate`, and the local
  KMS validation lock file.

## Follow-up work

Design a supported write-only secret path with an explicit minimum Terraform
version and test that values never enter logs or state. Separately bind
customer-approved parameter references to runtime identity and prove scoped
retrieval, rotation/revocation, and cleanup.
