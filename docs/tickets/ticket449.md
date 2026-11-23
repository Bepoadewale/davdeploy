# ticket449 — prove isolated SNS-to-SQS delivery

PR: https://github.com/Bepoadewale/davdeploy/pull/449
Branch: `test/nova-sns-sqs-delivery-449`

## Problem / goal

The `aws-jobs-events` capability currently has direct EventBridge-to-SQS and
Step Functions execution evidence, but no observed SNS delivery. Add a small,
reproducible same-account SNS-to-SQS test with queue authorization bound to one
exact topic ARN and account. Capture one synthetic delivery, then remove the
exact disposable stack and verify independent absence.

This is customer-side service evidence only. It does not dispatch through Nova,
modify the hosted control plane, or certify all `aws-jobs-events` behavior.

## Current repo state

- Backend `main` is `dcdcd07e09a912fe52763de4968cd9140d831979` (PR #448).
- PR #448's isolated SQS/Lambda/DynamoDB idempotency and recovery stack is
  destroyed; AWS absence and empty local state are recorded in `test448.md`.
- Existing `test257.md` records EventBridge-to-SQS delivery; `test256.md`
  records a Step Functions execution. SNS delivery, subscription authorization,
  and notification cost coverage remain open.
- This test is independent of hosted control-plane, Terraform state/lock,
  production resource, and Nova execution state.

## Research / references used

- [`test257.md`](../test/test257.md) — existing EventBridge-to-SQS delivery
  evidence.
- AWS [SNS delivery to SQS](https://docs.aws.amazon.com/sns/latest/dg/sns-sqs-as-subscriber.html) — topic subscription and queue-policy requirements.
- AWS [SQS access policy examples](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-basic-examples-of-sqs-policies.html) — restricting `SendMessage` with the SNS service principal and source ARN.
- HashiCorp AWS provider [`aws_sns_topic_subscription`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic_subscription), [`aws_sqs_queue_policy`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sqs_queue_policy), and [`aws_sns_topic`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic).

## Work planned for the PR

1. Add a pinned Terraform fixture and body-redacting Python probe.
2. Open this draft PR with its ticket and test record before AWS mutation.
3. Create one tagged topic, one SQS queue with SQS-managed encryption, one
   queue policy permitting `sqs:SendMessage` only from the exact topic ARN and
   trusted account, and one raw-message SQS subscription. Derive the ARNs from
   the verified caller, region, and fixed test names so the full policy is
   reviewable in the saved plan before apply.
4. Verify a synthetic message reaches the queue and matches the expected
   payload without printing its body. Delete the received message.
5. Review saved create and destroy plans; run all mutations through the PID
   monitor and use only the exact test prefix.
6. Independently confirm topic, queue, subscription, policy, and local state
   are gone after teardown; record all evidence and limitations.

## Acceptance criteria

- [x] Draft PR and matching ticket/test evidence exist before any AWS write.
- [x] Caller identity, region, exact names, and absence of conflicts are
      verified before create.
- [x] The saved plan contains only the four intended test resources and no
      changes or destroys; the complete queue policy names the exact planned
      queue ARN, topic ARN, account, and SNS service principal.
- [ ] Queue authorization allows only the exact SNS service principal, topic
      ARN, and account.
- [ ] A synthetic publish is received exactly once with matching content; the
      probe output omits the message body.
- [ ] Monitored destroy succeeds; AWS confirms all exact resources absent and
      the run monitor has no active work.
- [ ] Focused validation, docs convention checks, and all seven PR checks pass.
- [ ] Evidence is described as direct same-account SNS/SQS behavior and does
      not claim Nova dispatch, hosted execution, or complete scenario support.

## Boundaries

Use only `davdeploy-nova-sns-sqs-449-nov23a1` in account `654654474502`, region
`us-east-1`. Keep Terraform state and generated files outside the repository.
Use the PID-based Terraform monitor for every apply/destroy and never overlap
mutations. Do not read or print credentials or message bodies. Do not touch
production resources, control-plane runtime/state/locks, Nova gates, or customer
credentials. Preserve protected untracked files and retained lineage evidence.

## Acceptance status

Draft PR #449 was opened before any AWS mutation. The verified caller is
account `654654474502` in `us-east-1`; the exact topic and queue names were
absent and the run monitor had 24 terminal records with no active operation.
The reviewed saved create plan contains exactly four creates, zero changes,
and zero destroys. Its complete queue policy is known in plan and restricts
`sqs:SendMessage` to the exact test queue ARN, exact topic ARN, account, and
SNS service principal. The first monitored create attempt
`nova-sns-sqs-449-create-nov23a1` failed at STS credential validation because
its request signature was stale; it made no resource changes. Exact AWS reads
confirmed the topic and queue remained absent. A fresh plan was saved and
monitored create `nova-sns-sqs-449-create2-nov23a1` is running.

## Tests / validation performed

Terraform format and validation, Python syntax/Ruff, and documentation
conventions passed locally. Initial PR CI run `45085442555` passed all seven
checks on the first fixture revision; PR run `45085892273` passed all seven
checks on the reviewed known-ARN policy refinement. The first create attempt
failed before resource changes because of a stale STS signature. A fresh saved
plan is being applied through the monitor; its result is pending.

## Evidence files produced

- `docs/tickets/ticket449.md`
- `docs/test/test449.md`
- `docs/test/fixtures/nova-sns-sqs-delivery-449/main.tf`
- `docs/test/fixtures/nova-sns-sqs-delivery-449/probe.py`
- `docs/test/fixtures/nova-sns-sqs-delivery-449/.terraform.lock.hcl`

## Follow-up work

Policy coverage for SNS topic/endpoint authorization, confirmed delivery
behavior for SES, other event producers/consumers, notification pricing, and
Nova-originated `aws-jobs-events` execution remain separate work.
