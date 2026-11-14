# ticket411
PR: #411
Branch: feat/nova-rds-instance-pricing-411

## Problem / goal

Add conservative monthly pricing for a bounded RDS for MySQL configuration using live regional AWS Price List data. Bind backup usage assumptions from the integrity-checked customer revision into generated-plan pricing evidence and approval checks.

## Current repo state

PR #411 is a draft based on main commit 01895d6b6ceb7d69837187e3c19c0a5cd5033830. The plan-only Nova runner exists. Exact-plan apply remains fail-closed and unwired under draft PR #399.

## Research / references used

- AWS Price List API / Botocore price catalog interface used by the existing pricing implementation.
- AWS RDS pricing: https://aws.amazon.com/rds/pricing/
- RDS automated backup storage: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html
- RDS storage options: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html

## Work planned for the PR

- Price RDS MySQL M/R non-burstable, private Single-AZ, GP3 instance/storage configurations.
- Require explicit monthly backup storage usage bounds and report a range that reflects the shared account-level free allowance.
- Reject unsupported or unknown price-driving and safety fields.
- Persist assumptions through customer revisions and expose the input in the API contract.
- Bind assumptions into approval context digests and add hosted regression coverage.
- Verify with required GitHub Actions checks; do not run or claim a workload apply.

## Acceptance criteria

- A supported RDS plan has complete instance, storage, and backup price evidence from exact regional catalog mappings.
- Missing usage assumptions, unsupported settings, and material unknown values block approval before price lookup.
- Changing persisted RDS assumptions invalidates approval eligibility.
- OpenAPI includes the persisted constraint.
- Hosted required CI passes on final PR head.

## Acceptance status

Implementation and API contract are verified by hosted CI. Run 43644240047 passed all seven checks on commit ad64375d179c5586dd16bda37747b8818a0999b5. No AWS workload was applied.

## Tests / validation performed

- Added tests for pricing ranges, persisted-context extraction, digest binding, unsupported configurations, and missing assumptions.
- GitHub Actions runs 43643826938 and 43644240047 passed all seven required checks (latest recorded commit ad64375d179c5586dd16bda37747b8818a0999b5).
- The hosted Python job passed 1,226 tests; hosted end-to-end verification including API contract and OpenAPI checks passed.
- An earlier docs convention failure was corrected before the passing run.
- No local test commands or AWS workload commands were run.

## Evidence files produced

- docs/test/test411.md

## Boundaries

Supports only RDS MySQL non-burstable M/R, private Single-AZ, GP3 storage with explicit usage bounds. Backup charge is estimated from zero to full declared usage due to account-level allowance. This does not cover multi-AZ, burstable instances, customer-managed KMS, monitoring, log exports, restore, transfer, or every RDS configuration. Estimates are not a bill forecast or spend cap.

## Follow-up work

Complete required hosted validation, then continue actual-plan policy, protected saved-plan storage, and generic hosted worker wiring. Do not enable the apply boundary or claim customer lifecycle certification.
