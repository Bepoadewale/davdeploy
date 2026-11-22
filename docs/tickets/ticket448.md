# ticket448 — isolated SQS success, idempotency, and redrive recovery

PR: https://github.com/Bepoadewale/davdeploy/pull/448
Branch: `test/nova-sqs-lambda-idempotency-448`

## Problem / goal

PR #447 proved a failing Lambda consumer retries an SQS message into its paired
DLQ, then cleaned up the test stack. The next SQS lifecycle gap is whether a
successful consumer can apply a duplicate-safe side effect, and whether a
failed message can be redriven and processed after a code update.

Build a reproducible, disposable same-account test fixture for an SQS source
and DLQ, a Lambda consumer, and a DynamoDB idempotency ledger. Record direct
AWS evidence for duplicate suppression, v1-to-v2 code update, DLQ redrive, and
recovery. This does not use Nova dispatch or touch the hosted control plane.

## Current repo state

- Backend `main` is `78d11f82a373797f5d0c739956b93b3b618796dc` (PR #447).
- PR #445's SQS policy is merged in source, not deployed to the control plane.
- PR #446 fixed source-after-DLQ ordering. PR #447 recorded real Lambda
  failure/retry/DLQ delivery and confirmed teardown.
- Direct ECS Express lifecycle evidence from PR #437 remains accepted as the
  general customer-side plan/apply/health/update/recovery/teardown gate.
- AWS account `654654474502`, region `us-east-1`; this test will use only
  `davdeploy-nova-sqs-idem-448-nov23a1` resource names.
- The test has no hosted control-plane, Terraform state/lock, production
  resource, or Nova execution dependency.

## Research / references used

- [`test447.md`](../test/test447.md) — direct Lambda retry-to-DLQ evidence and
  cleanup.
- AWS [SQS to Lambda configuration](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-configure-lambda-function-trigger.html) — visibility timeout and DLQ behavior.
- AWS [StartMessageMoveTask](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_StartMessageMoveTask.html) — managed DLQ-to-source redrive.
- AWS [DynamoDB PutItem](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_PutItem.html) — conditional writes with `attribute_not_exists`.
- AWS [Lambda SQS integration](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html) — at-least-once delivery and idempotent consumer requirements.

## Work planned for the PR

1. Add a reviewable Terraform/Python fixture under `docs/test/fixtures/`;
   provider versions are pinned and test state stays outside the repository.
2. Open a draft PR with ticket and test evidence before any AWS mutation.
3. Create one tagged SQS source/DLQ pair, a DynamoDB idempotency table, and a
   Lambda role limited to source receive/delete/attributes plus `PutItem` on
   that exact table. Use a three-second function timeout and 30-second source
   visibility timeout.
4. With v1, send two messages carrying the same synthetic idempotency key and
   verify there is one ledger item. Send a controlled-failure event, verify
   retry to the paired DLQ, and review an update plan changing only Lambda code.
5. Apply v2 through the Terraform run monitor, redrive the failed message to
   the source queue with SQS `StartMessageMoveTask`, and verify the ledger has
   the recovered key once with v2. Send the same key again and verify no
   overwrite or duplicate record.
6. Review and run a saved destroy plan through the PID monitor. Independently
   verify all exact test resources are absent, including any generated logs.
7. Record operation IDs, run IDs, metric/data observations, cleanup, and the
   limitations in `docs/test/test448.md`.

## Acceptance criteria

- [x] Draft PR and matching ticket/test evidence exist before any AWS write.
- [x] Caller identity is account `654654474502`; test resources are uniquely
      prefixed/tagged and no production/control-plane resources change.
- [x] The successful v1 consumer writes one item for two messages with the
      same idempotency key; the duplicate is acknowledged without overwriting.
- [x] A controlled failure exceeds `maxReceiveCount=5` and is delivered to the
      exact paired DLQ.
- [x] The saved v1-to-v2 Terraform plan changes only the test Lambda code.
- [x] SQS-managed DLQ redrive returns the failed event to the source; v2 writes
      one ledger item for it and acknowledges a duplicate without overwrite.
- [x] Monitored destroy succeeds, local state is empty, exact AWS resources are
      independently confirmed absent, and the run monitor has no active work.
- [x] Focused fixture validation, documentation conventions, and all seven
      required PR checks pass.
- [x] Evidence is described as direct same-account service behavior. It does
      not claim Nova dispatch, cross-account isolation, hosted execution, or
      broad customer certification.

## Acceptance status

PR #448 is a draft. The caller is verified in account `654654474502`; the
exact test prefix was absent before apply. The reviewed saved plan contained
exactly seven creates and zero changes/destroys. Monitored apply
`nova-sqs-idem-448-create-nov23a1` succeeded with seven added, zero changed,
and zero destroyed. The SQS mapping is Enabled and the Lambda is Active.
Two success messages with the same key were acknowledged; DynamoDB contains
exactly one `v1` ledger item. The controlled-failure message reached the paired
DLQ at receive count six. Monitored v1-to-v2 update succeeded with one change.
SQS redrive task `463e6401-e6a4-438d-b375-be3d6d9e56c0` completed, moving one
message. V2 wrote one `redrive-recovery-001` item and acknowledged a duplicate
without overwriting it. The table contains two records total. The reviewed
seven-delete plan ran through the Terraform monitor and succeeded with zero
adds, zero changes, and seven destroys. After the required five-minute wait,
independent AWS reads confirmed the exact source/DLQ queues, DynamoDB table,
Lambda function, event source mapping, IAM role, and generated Lambda log
group absent. The local Terraform state is empty; the run monitor has 24
terminal records and no active work.

## Tests / validation performed

`terraform fmt -check`, provider initialization, `terraform validate`, and
Python syntax checks passed locally. Before any AWS write, a reviewed saved
plan contains seven test resources and no changes or destroys. Its exact inline
policy grants the source queue's three receive/delete/attributes actions and
`dynamodb:PutItem` on only the computed test table ARN. The source queue uses
30-second visibility for the three-second Lambda and max receive count five.
The v1 create added seven test resources with no updates or deletes. The v2
saved update plan contains one in-place Lambda change, with six no-op
resources and no replacements. Monitored update
`nova-sqs-idem-448-update-nov23a1` started at `2026-11-22T23:15:42Z` with
supervisor PID 93804, root
`/private/tmp/davdeploy-nova-sqs-idem-448-nov23a1`, and log
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-idem-448-update-nov23a1.log`.
Terraform PID 93805; it finished successfully at `2026-11-22T23:15:57Z` with
zero added, one changed, and zero destroyed. SQS redrive task
`463e6401-e6a4-438d-b375-be3d6d9e56c0` completed and moved one message. The
v2 recovery key remains one `v2` record after a later duplicate. The table
contains two records; source and DLQ have no visible messages. Reviewed
`destroy-reviewed.tfplan` contains exactly seven deletes, zero adds, and zero
updates. Monitored destroy `nova-sqs-idem-448-destroy-nov23a1` started at
`2026-11-22T23:25:24Z` with supervisor PID 96678, root
`/private/tmp/davdeploy-nova-sqs-idem-448-nov23a1`, and log
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-idem-448-destroy-nov23a1.log`.
It completed at `2026-11-22T23:25:40Z` with zero added, zero changed, and seven
destroyed. After waiting more than five minutes, exact AWS queue/table/Lambda/
mapping/role/log-group lookups returned no resources; the local state is
empty. The monitor has 24 terminal records and zero active operations.
`GITHUB_PR_NUMBER=448 python3 scripts/check_doc_conventions.py` and all seven
required PR checks passed; final CI run `45083356874` is on head
`3d1f6de2a1d671e1ed70106c8d880fd22d5bde29`.

## Evidence files produced

- `docs/tickets/ticket448.md`
- `docs/test/test448.md`
- `docs/test/fixtures/nova-sqs-lambda-idempotency-448/main.tf`
- `docs/test/fixtures/nova-sqs-lambda-idempotency-448/.terraform.lock.hcl`
- `docs/test/fixtures/nova-sqs-lambda-idempotency-448/consumer_v1.py`
- `docs/test/fixtures/nova-sqs-lambda-idempotency-448/consumer_v2.py`

## Boundaries

Use only `davdeploy-nova-sqs-idem-448-nov23a1` in account `654654474502`,
region `us-east-1`. Keep Terraform state and generated zip in a separate `/tmp`
directory. Use the PID-based Terraform run monitor for all applies/destroys;
never overlap mutations on the root. Preserve synthetic messages and test
data only; keep credentials and message bodies out of logs. Do not touch
production queues, control-plane runtime/state/locks, Nova gates, or customer
credentials. Clean up only the exact test stack and generated test artifacts.

## Follow-up work

This test adds direct SQS/Lambda idempotency and redrive recovery evidence. It
does not close Nova-originated execution, cross-account trust, KMS-backed SQS,
all 26 architecture entries, all 30 Terraform roots, or complete cost coverage.
