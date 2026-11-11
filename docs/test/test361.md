# test361 — RDS backup retention and final snapshot policy

Date: 2026-11-11

Execution type: local unit tests and isolated local proof only. No AWS plan,
apply, destroy, or customer workload was run.

Test ID: `pr361-rds-retention-policy`.

Repository: `Bepoadewale/davdeploy`, branch `security/rds-retention-policy-361`.

Customer repository: None. Plan documents are synthetic local fixtures.

Commit: Pending final implementation commit.

AWS account: None. No AWS session was used.

AWS region: None.

## Scope

This evidence covers fail-closed validation of RDS backup-retention values,
explicit human review when an RDS instance disables automated backups, and
review or denial outcomes for RDS replacements according to final-snapshot
settings. The generated-plan policy version was advanced. This is not hosted
Nova execution evidence.

## Local verification

- Focused command: `.venv/bin/python -m pytest tests/test_generated_plan_policy.py -q` — 131 passed.
- Ruff: `.venv/bin/ruff check apps/api/src tests scripts` — passed.
- `make verify` — 986 passed; Ruff, Actions configuration, OpenAPI snapshot,
  and Compose configuration passed.
- `make local-proof` — local stack readiness, API/CORS contract, customer-plan
  E2E, fixture seeding, trace check, and the full verification suite passed
  (986 tests).
- `python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.

## Resources created

No AWS resources. `make local-proof` created an isolated Docker Compose project
named `davdeploy-pr361` and its local Postgres volume for the proof. The stack
is stopped after verification; its local volume is retained. No repository
worktree, volume, image, or file was deleted.

## Commands executed

The focused test, lint, full verification, and clean-room local proof commands
listed above. No Terraform or AWS CLI command was run.

## Observed result

The policy denies missing, malformed, out-of-range and unknown RDS retention
values. An `aws_db_instance` with retention set to zero receives a human-review
finding. A valid positive RDS cluster retention remains eligible for human
review. RDS replacement without a final snapshot receives an explicit review
finding; invalid snapshot metadata or a missing identifier when a snapshot is
required is denied.

## Teardown

The isolated Compose services were stopped after the proof. The local database
volume remains for reproducibility; no deletion was performed.

## Final boundary

This is local security-policy evidence only. It does not demonstrate live AWS
planning, regional pricing, hosted Nova requests, approval, apply, application
health, recovery, data restoration, or customer teardown.
