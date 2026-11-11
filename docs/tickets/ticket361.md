# ticket361 — enforce explicit RDS backup and snapshot safety

PR: [#361](https://github.com/Bepoadewale/davdeploy/pull/361) (draft; number reserved)
Branch: `security/rds-retention-policy-361`
Base: `main`

## Problem / goal

Harden actual generated Terraform plan policy for RDS data retention. Unknown or
malformed backup-retention settings must fail closed. Disabled automated
backups and deletion without a final snapshot must be visible as explicit
human-review findings. Preserve valid, explicitly reviewed temporary-workload
flows and keep all Nova execution gates disabled.

## Current repo state

- Backend `main` is `31fe14147182e830b69d3d9a97c2d8d67932e00c`; its merged-main
  CI run `43105046826` passed all seven jobs.
- `POLICY_CRITICAL_UNKNOWN_PATHS` currently covers RDS encryption, publicness,
  deletion protection and `skip_final_snapshot`, but not
  `backup_retention_period`.
- `_check_databases` denies public RDS resources and unknown encryption but
  does not validate backup-retention values or report when automated backups
  are disabled. General deletion/replacement already requires human review.
- No customer Nova plan or workload has been applied, operated, or certified.

## Research / references used

- AWS RDS backup retention: <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.BackupRetention.html>
- Terraform AWS `aws_db_instance`: <https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance>
- Terraform AWS `aws_rds_cluster`: <https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/rds_cluster>
- Current policy implementation: `apps/api/src/davdeploy/generated_plan_policy.py`.
- Actual-plan security tests: `tests/test_generated_plan_policy.py`.

## Work planned for the PR

- Treat `backup_retention_period` as a critical plan value for RDS instances and
  clusters, including unknown-value metadata.
- Fail closed for missing, malformed, or unsupported retention values.
- Require explicit human review when an RDS instance disables automated
  backups; enforce a supported positive retention range for RDS clusters.
- For RDS deletes and replacements, inspect the prior planned state and emit
  an explicit review finding if the final snapshot is skipped; fail closed if
  snapshot behavior cannot be established safely.
- Bump the generated-plan policy version and add positive and negative actual
  Terraform plan regressions. Keep general destructive-change review intact.

## Acceptance criteria

- [ ] Missing, malformed, out-of-range, and unknown RDS backup-retention values
  produce explicit denial outcomes.
- [ ] An RDS instance with automated backups disabled requires human review.
- [ ] RDS delete/replacement plans that skip or cannot safely establish final
  snapshot behavior produce explicit outcomes; normal final-snapshot plans keep
  their existing destructive-change review.
- [ ] Existing safe RDS plan cases and unrelated policy tests remain valid.
- [ ] Focused tests, full `make verify`, clean-room `make local-proof`, docs
  conventions, and diff checks pass.
- [ ] Required final-head GitHub CI passes before merge.
- [ ] No runtime gate is enabled and no AWS/customer infrastructure is changed.

## Acceptance status

Implemented and locally verified; final-head pull request checks remain a merge
gate. The change adds critical unknown-value checks, bounded retention
validation, explicit review for disabled instance backups and RDS replacement
without a final snapshot, plus fail-closed snapshot metadata checks.

## Tests / validation performed

- Focused generated-plan policy suite: 131 passed.
- `make verify`: 986 passed; Ruff, Actions configuration, OpenAPI snapshot,
  and Compose configuration passed.
- `make local-proof`: local stack readiness, API/CORS contract, customer-plan
  E2E, fixture seeding, trace check, and `make verify` passed (986 tests).
- Documentation convention and diff checks are recorded in `docs/test/test361.md`.
- No AWS workload test or infrastructure mutation was performed.

## Evidence files produced

`docs/test/test361.md` will record local verification and the non-AWS execution
boundary required for a runnable PR.

## Boundaries

This PR changes actual-plan security policy and tests only. It does not
integrate pricing, enable plan generation, install a customer role, dispatch a
hosted plan, or add customer apply/destroy behavior. PR #318 pricing work stays
closed and held.

## Follow-up work

Continue tenant-role verification, hosted plan execution, price-bound plan
approval, exact saved-plan apply, health/recovery, retained-data restoration,
teardown, and composed scenario certification independently of this policy
change.
