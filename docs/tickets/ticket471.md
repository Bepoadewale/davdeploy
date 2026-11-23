# ticket471

PR: [#471 — feat: bind AppConfig environments to planned applications](https://github.com/Bepoadewale/davdeploy/pull/471) (draft)

Branch: `feat/appconfig-env-binding-471`

## Problem / goal

The feature-flags Terraform module creates an AppConfig application and an
environment, but generated-plan policy does not verify their binding. Add a
same-plan reference check so an environment cannot silently point at an
unplanned or different AppConfig application.

## Current repo state

- `infrastructure/terraform/modules/feature-flags/main.tf` creates an
  application and a production environment whose `application_id` references
  the application ID.
- The module does not create a configuration profile, hosted version, feature
  flag document, deployment strategy, or deployment.
- Generated-plan policy had no AppConfig-specific relationship checks.
- No root-specific AppConfig workload or lifecycle evidence exists.

## Research / references used

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/feature-flags/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Work planned for the PR

1. Require application and environment names to be known and non-empty.
2. Verify each planned environment binds through a Terraform configuration
   reference to exactly one same-plan AppConfig application, allowing for the
   computed application ID.
3. Deny missing, external, or ambiguous application bindings.
4. Add regression tests and clarify the limits of the feature-flags module in
   the evidence matrix.

## Acceptance criteria

- [x] A valid same-plan application/environment relationship remains eligible
  for human review.
- [x] An environment referencing an unplanned application is denied.
- [x] Unknown application or environment names are denied.
- [x] Regression tests cover valid, invalid, and unknown cases.
- [x] The capability matrix keeps actual flag creation, rollout, rollback,
  workload, lifecycle, and pricing evidence open.
- [x] No AWS or hosted control-plane resources are changed.
- [x] Focused and full policy tests, documentation conventions, Ruff, and
  `git diff --check` pass.
- [x] Final-head CI and review/merge state are tracked on PR #471; merge only
  after all required checks pass.

## Acceptance status

Implementation is complete on PR #471. The module still provisions only an
AppConfig application and environment; it does not deploy a feature flag.

## Tests / validation performed

- `tests/test_generated_plan_policy.py` — 400 passed.
- Ruff on changed Python files — passed.
- `GITHUB_PR_NUMBER=471 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Final-head CI is tracked on PR #471.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket471.md`

## Boundaries

- Source and documentation only; do not mutate AWS AppConfig resources.
- Do not access or change hosted control-plane resources.
- Do not claim a deployed feature flag, staged rollout, rollback, runtime
  fetch, customer lifecycle, or AppConfig pricing from this relationship check.
- Preserve `--only-show-errors`, `.venv-pr399/`,
  `docs/test/fixtures/nova-batch-retry-458/terraform.tfstate`, and generated
  provider lock files.

## Follow-up work

Design a complete feature-flag profile, version, strategy, and deployment
module. Then record customer-side flag fetch, staged rollout, alarm-driven
rollback, update, and cleanup evidence.
