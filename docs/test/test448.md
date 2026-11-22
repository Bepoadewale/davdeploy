# test448 — isolated SQS idempotency and redrive recovery

Date: 2026-11-23

Execution type: Controlled disposable AWS workload validation.

Repository: `Bepoadewale/davdeploy`

Customer repository: None; direct same-account AWS service test.

Commit: `807e667d9fe9e2dc45a66617b0a4b1165c4575d9` (fixture applied).

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The seven-resource test stack was created from the reviewed plan under the
unique `davdeploy-nova-sqs-idem-448-nov23a1` prefix.

## Commands executed

- Terraform fixture is included at
  `docs/test/fixtures/nova-sqs-lambda-idempotency-448/`.
- Draft PR #448 was opened before any AWS mutation.
- `terraform fmt -check`, provider initialization, and `terraform validate`
  passed against an isolated copy of the fixture under `/tmp`.
- Python syntax parsing passed for both Lambda versions.
- Draft PR #448 and its matching ticket/test evidence were present before any
  AWS write.
- Before apply, AWS caller was verified as account `654654474502`; the exact
  queue, table, Lambda, and role names were absent. The monitor then had 21
  terminal runs and no active operation.
- Saved plan `create-final.tfplan` contains seven creates, zero changes,
  and zero destroys. The plan-bound inline role policy is fully known and
  grants only the exact source queue actions and `PutItem` on the exact test
  table. Source visibility is 30 seconds for the three-second Lambda; the
  retry threshold is five.
- Monitored v1 create succeeded with seven added, zero changed, and zero
  destroyed. The event source mapping is Enabled, the Lambda is Active, and
  the DynamoDB table is ACTIVE with on-demand billing and encryption enabled.
- V1 create run `nova-sqs-idem-448-create-nov23a1` started at
  `2026-11-22T23:06:21Z`, supervisor PID 91188, Terraform PID 91189, root
  `/private/tmp/davdeploy-nova-sqs-idem-448-nov23a1`, and log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-idem-448-create-nov23a1.log`.
- Both success messages shared the same key. AWS reads found one table item
  with `consumer_version=v1` and zero source-queue visible messages.
- The controlled failure message ID `d8ac52f7-5a75-4246-b10f-9d6c0fb9794f`
  reached the exact paired DLQ with `ApproximateReceiveCount=6`.
- Reviewed saved v2 update plan `update-reviewed.tfplan`: exactly one in-place
  update to the Lambda function; the other six resources are no-op, with no
  creates or destroys. Monitored update run `nova-sqs-idem-448-update-nov23a1`
  started at `2026-11-22T23:15:42Z`, supervisor PID 93804, Terraform PID
  93805, root `/private/tmp/davdeploy-nova-sqs-idem-448-nov23a1`, and log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-idem-448-update-nov23a1.log`.
  It succeeded at `2026-11-22T23:15:57Z` with zero added, one changed, and
  zero destroyed. The Lambda is Active with handler `consumer_v2.handler` and
  the event source mapping remains Enabled.
- SQS redrive task `463e6401-e6a4-438d-b375-be3d6d9e56c0` completed with one
  message moved. V2 created exactly one `redrive-recovery-001` ledger item
  with `consumer_version=v2`. After sending duplicate message
  `cf3edfef-9578-4a2d-bdd0-fbd11ce5cf9b`, the item remained `v2` and table
  count remained two. Source and DLQ both had zero visible messages; source
  had zero in-flight messages.
- Sent success message IDs
  `310fd3c9-c5ec-4454-a2f8-d839ea77edaa` and
  `9bcee1e2-beae-4446-82be-1c3524d18eb2`, both using the same synthetic key.
  DynamoDB contains exactly one item with `consumer_version=v1`; the source
  queue has no visible message.
- Sent controlled-failure message ID `d8ac52f7-5a75-4246-b10f-9d6c0fb9794f`.
  It reached the DLQ at receive count six.
- The reviewed saved destroy plan `destroy-reviewed.tfplan` contains exactly
  seven deletes, zero creates, and zero updates. Monitored destroy run
  `nova-sqs-idem-448-destroy-nov23a1` started at `2026-11-22T23:25:24Z`,
  supervisor PID 96678, root
  `/private/tmp/davdeploy-nova-sqs-idem-448-nov23a1`, and log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-idem-448-destroy-nov23a1.log`.
  Terraform PID 96679; it completed at `2026-11-22T23:25:40Z` with zero
  added, zero changed, and seven destroyed. The local state is empty. After
  waiting more than five minutes, independent AWS reads confirmed the exact
  source/DLQ queues, table, Lambda function, event source mapping, IAM role,
  and generated Lambda log group absent. The run monitor has 24 terminal
  records and zero active operations. PR CI run `45083356874` passed all seven
  checks on head `3d1f6de2a1d671e1ed70106c8d880fd22d5bde29`.

## Observed result

The v1 consumer acknowledged both success messages with the same idempotency
key while DynamoDB retained exactly one `v1` record. The failing message
reached the exact paired DLQ at receive count six. The reviewed v1-to-v2 plan
changed only the Lambda function. AWS managed redrive completed one move back
to the source queue; v2 created one `redrive-recovery-001` record with version
`v2`. A subsequent duplicate was acknowledged without overwriting the item;
the table remained at two records. Source and DLQ had zero visible messages,
and the source had zero in-flight messages.

## Teardown

The reviewed exact seven-resource destroy plan succeeded through the PID
monitor. Independent AWS reads after the settling period confirmed every
resource absent, local state is empty, and the run monitor has no active work.

## Final boundary

This direct same-account service test does not establish Nova dispatch,
cross-account isolation, hosted execution, or customer workload certification.
The hosted control plane, its Terraform state/locks, production queues, and
Nova execution gates are not part of this test.
