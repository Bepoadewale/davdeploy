# ticket305 — Reconcile historical validation cleanup evidence

PR: https://github.com/Bepoadewale/davdeploy/pull/305
Branch: `docs/reconcile-validation-cleanup-evidence`

## Problem / goal

The local Terraform monitor reports historical runs as `FINISHED_UNKNOWN_EXIT`.
That state does not prove success or failure. Reconcile the monitor records and
logs with current AWS resources so the execution goal records whether disposable
certification resources remain, without rewriting uncertain exit statuses.

## Current repo state

- PR #304 reconciled current GitHub and hosted deployment versions.
- The local monitor registry has historical unknown-exit records and no active
  Terraform process.
- AWS account `654654474502`, region `us-east-1`, was queried read-only using
  the authorized local AWS profile.

## Research / references used

- `scripts/terraform_run_monitor.py` and its local run registry/logs.
- `docs/test/test261.md`, `docs/test/test262.md`, `docs/test/test263.md`, and
  the module-validation Terraform roots.
- AWS Resource Groups Tagging API, SageMaker, Batch, S3, ECR, EC2, VPN,
  OpenSearch Serverless and Bedrock read-only queries.
- Goal handoff and readiness matrix.

## Work planned for the PR

- Record that monitor process state is historical/unknown and must not be
  promoted to successful exit status merely from absent PIDs.
- Record current tagged certification resource inventory and its non-billable
  residual states.
- Update the durable goal handoff from the observed evidence.
- Do not delete, deregister or rewrite any resource or historical run record.

## Acceptance criteria

- [x] Active Terraform operations are distinguished from old unknown-exit runs.
- [x] Remaining test-tagged resources are enumerated with exact type/status.
- [x] Absent test workloads are described only for directly queried resources.
- [x] No unknown process exit is rewritten as success.
- [x] The goal handoff links the exact audit and says what remains to reconcile.
- [x] Documentation convention and diff checks pass.

## Acceptance status

Pending validation. Read-only inventory found no active infrastructure among
resources tagged `Purpose=davdeploy-module-validation`; only inactive Batch
job-definition records and SageMaker lineage records already in `DELETING`
remain. The monitor records remain `FINISHED_UNKNOWN_EXIT`.

## Tests / validation performed

`GITHUB_PR_NUMBER=305 python3 scripts/check_doc_conventions.py` and
`git diff --check` passed. The monitor registry contains 40 records, all
`FINISHED_UNKNOWN_EXIT`; no process matched Terraform apply, destroy or monitor
supervisor commands. The Resource Groups Tagging API returned six tagged
records: four Batch job definitions with `INACTIVE` status and two SageMaker
lineage records whose associated resources show `DELETING`. The same inventory
contained no other resources with the module-validation purpose tag. Exact
read-only probes found the test Knowledge Base/OpenSearch collection, VPN
connections/customer gateway/EC2 peers, `davdeploy-cert*` S3 buckets and
certification ECR repositories absent. No cloud mutation was performed.

## Evidence files produced

No `docs/test/test305.md` is required: this PR performs no customer workload
operation and makes no cloud change.

## Boundaries

This PR does not destroy AWS resources, delete historical logs, change the
monitor registry or claim that all historical operations exited successfully.

## Follow-up work

Fix monitor status recording if current-version operations still finish as
unknown. Keep the remaining inactive/deleting SageMaker and Batch records
classified as test metadata unless a separate verified cleanup need arises.
