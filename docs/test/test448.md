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
- AWS caller is verified as account `654654474502`; the exact queue, table,
  Lambda, and role names are absent, and the monitor has 21 terminal runs with
  no active operation.
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
  started at `2026-11-22T23:15:42Z` with supervisor PID 93804, root
  `/private/tmp/davdeploy-nova-sqs-idem-448-nov23a1`, and log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-idem-448-update-nov23a1.log`.
  Its final result is pending.
- Sent success message IDs
  `310fd3c9-c5ec-4454-a2f8-d839ea77edaa` and
  `9bcee1e2-beae-4446-82be-1c3524d18eb2`, both using the same synthetic key.
  DynamoDB contains exactly one item with `consumer_version=v1`; the source
  queue has no visible message.
- Sent controlled-failure message ID `d8ac52f7-5a75-4246-b10f-9d6c0fb9794f`.
  It remains in the source retry cycle; DLQ transition and subsequent update,
  redrive, and destroy evidence are pending.

## Observed result

The successful v1 path acknowledged two messages with the same key and
created one DynamoDB record. The controlled failure remains in the source
queue retry cycle; DLQ delivery, Lambda update, managed redrive, and recovery
The source queue/DLQ and Lambda mapping are active. V1 processed both duplicate
success messages while the idempotency table retained exactly one `v1` item.
The controlled failure reached the paired DLQ after six receives. The v2
update plan changes only the Lambda; redrive/recovery and cleanup remain
pending.

## Teardown

Pending. The named seven-resource stack remains under test until lifecycle
evidence is complete; cleanup will use a reviewed saved plan and PID monitor.

## Final boundary

This direct same-account service test does not establish Nova dispatch,
cross-account isolation, hosted execution, or customer workload certification.
The hosted control plane, its Terraform state/locks, production queues, and
Nova execution gates are not part of this test.
