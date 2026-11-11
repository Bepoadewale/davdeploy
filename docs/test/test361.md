# test361 — RDS backup retention and final snapshot policy

Date: 2026-11-11

Execution type: local unit tests and isolated local proof, followed by a
protected control-plane Terraform plan and exact saved-plan apply. This was not
a Nova customer workload test.

Test ID: `pr361-rds-retention-policy`.

Repository: `Bepoadewale/davdeploy`; PR #361 source branch
`security/rds-retention-policy-361` is merged and deleted.

Customer repository: None. Policy tests use synthetic plan documents; the
protected release changed only DavDeploy control-plane Lambda packages.

Commit: `5775d766584f31f8a31b6b22e8e523b4e8a3f257` (PR #361 merge commit and
deployed control-plane source). Local implementation verification ran on
source commit `96f149f804aa270aeb0fc4d3ec2bcee2f099167a`.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Scope

This evidence covers fail-closed validation of RDS backup-retention values,
explicit human review when an RDS instance disables automated backups, and
review or denial outcomes for RDS deletes/replacements according to
final-snapshot settings. The generated-plan policy version was advanced and
deployed as control-plane code. This is not hosted Nova execution evidence.

## Local verification

- Focused command: `.venv/bin/python -m pytest tests/test_generated_plan_policy.py -q` — 131 passed.
- Ruff: `.venv/bin/ruff check apps/api/src tests scripts` — passed.
- `make verify` — 986 passed; Ruff, Actions configuration, OpenAPI snapshot,
  and Compose configuration passed.
- `make local-proof` — local stack readiness, API/CORS contract, customer-plan
  E2E, fixture seeding, trace check, and the full verification suite passed
  (986 tests).
- `python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Final-head PR CI run [43109585051](https://github.com/Bepoadewale/davdeploy/actions/runs/43109585051)
  passed all seven jobs on head `23c0e305052885f4dff40836896fe4823f2fbfb2`;
  current-head Codex review reported no major issues. Merged-main CI run
  `43110311710` passed all seven jobs.

## Resources created

No customer AWS resources. Protected apply updated six existing DavDeploy
control-plane Lambda packages in place (0 additions, 6 updates, 0 destroys).
`make local-proof` created an isolated Docker Compose project named
`davdeploy-pr361` and its local Postgres volume. The stack is stopped after
verification; its local volume is retained. No repository worktree, volume,
image, or file was deleted.

## Commands executed

The focused test, lint, full verification, and clean-room local proof commands
listed above. The protected release sequence was:

- Terraform plan run [43111051028](https://github.com/Bepoadewale/davdeploy/actions/runs/43111051028)
  for exact commit `5775d766584f31f8a31b6b22e8e523b4e8a3f257`.
- Exact saved-plan apply run [43112125588](https://github.com/Bepoadewale/davdeploy/actions/runs/43112125588),
  deployment `7722764924`, approved under the account owner's standing
  instruction after reviewing the bounded plan summary and disabled Nova gates.
- Read-only AWS identity, six allowlisted Lambda configuration queries, and
  `curl -fsS https://api.davdeploy.tech/healthz`.

No customer-workload Terraform plan, apply, or destroy was run.

## Observed result

The policy denies missing, malformed, out-of-range and unknown RDS retention
values. An `aws_db_instance` with retention set to zero receives a human-review
finding. A valid positive RDS cluster retention remains eligible for human
review. RDS replacement without a final snapshot receives an explicit review
finding; delete and replacement cases with invalid snapshot metadata or a
missing identifier when a snapshot is required are denied.

Protected plan `43111051028` was complete/applyable with no errors: 0 adds, 6
in-place Lambda updates, 0 destroys/replacements/other, 0 drift, and 8 output
changes. The six functions were `api`, `cognito_email_sender`, `cognito_link`,
`migrate`, `policy`, and `worker`. Plan summary gates for runner, role
verification, broker, plan review, state, and hosted certification were all
false; legacy cloud-execution and `ALLOW_CLOUD_PLAN`/`ALLOW_CLOUD_APPLY` were
true and remain distinct from the Nova gates.

Apply `43112125588` succeeded for the exact saved plan and merge commit.
Database migration verification succeeded after one retry while Aurora
resumed. All six control-plane Lambdas are Active with successful updates and
common `CodeSha256=29j5jv6Gefv883KmJnN2DyKTo8VH9Ma8pck8uE63AHQ=`. The API
health endpoint returned `{"status":"ok","product":"davdeploy"}`.

## Teardown

The isolated Compose services were stopped after the proof. The local database
volume remains for reproducibility; no deletion was performed. No AWS
customer/test resources were created, so no cloud teardown was needed.

## Final boundary

The RDS security policy is deployed in the DavDeploy control plane. This does
not demonstrate live customer AWS planning, regional pricing, a hosted Nova
request, cost-bound customer approval, customer apply, application health,
recovery, data restoration, or teardown.
