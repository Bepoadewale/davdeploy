# test449 — isolated SNS-to-SQS delivery

Date: 2026-11-23

Execution type: Controlled disposable AWS workload validation.

Customer repository: None; direct same-account AWS service test.

Commit: `7495c2ad064fab07cb1298b58f66827850abb138` (known-ARN policy plan).

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The test created one SNS topic, one SQS queue, one SQS queue policy, and one
SNS subscription under the unique `davdeploy-nova-sns-sqs-449-nov23a1` prefix.
The reviewed teardown removed all four. Terraform state and generated files
stay outside the repository.

## Commands executed

- Draft PR #449 and matching ticket/test evidence were opened before any AWS
  mutation.
- Caller verified as account `654654474502`, region `us-east-1`. Exact topic
  and queue names were absent; the run monitor had 24 terminal entries and no
  active operation.
- Terraform init selected AWS provider `5.100.0`; format, validation, Python
  syntax/Ruff, and documentation conventions passed locally.
- Saved plan `create-reviewed2.tfplan` contains exactly four creates, zero
  changes, and zero destroys. Its full queue policy is known before apply and
  names the exact topic ARN, queue ARN, account, and SNS service principal.
- Initial PR CI run `45085442555` passed all seven checks on the first fixture
  revision. Final fixture run `45085892273` also passed all seven checks on
  commit `7495c2ad064fab07cb1298b58f66827850abb138`.
- The first monitored create `nova-sns-sqs-449-create-nov23a1` started at
  `2026-11-23T02:54:13Z` (supervisor PID 7937, Terraform PID 7938, root
  `/private/tmp/davdeploy-nova-sns-sqs-449-nov23a1`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sns-sqs-449-create-nov23a1.log`). It failed at
  `2026-11-23T03:09:48Z` while validating an STS request whose signature was
  stale by 15 minutes. It made no resource changes; fresh exact-name AWS reads
  confirmed the topic and queue remained absent.
- After confirming caller identity again, a fresh four-create plan was saved
  as `/tmp/davdeploy-nova-sns-sqs-449-nov23a1/create-reviewed2.tfplan`. The
  exact topic/queue policy remains fully known. Monitored create
  `nova-sns-sqs-449-create2-nov23a1` started at `2026-11-23T14:35:40Z`,
  supervisor PID 13106, root
  `/private/tmp/davdeploy-nova-sns-sqs-449-nov23a1`, and log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sns-sqs-449-create2-nov23a1.log`. Terraform PID 13107; it completed at
  `2026-11-23T14:36:38Z` with four added, zero changed, and zero destroyed.
- AWS confirmed one SNS-to-SQS subscription with a non-pending ARN and one
  confirmed topic subscription. The probe published one synthetic message,
  received it once, matched the expected JSON, and deleted it. Probe output
  contained only a success flag and receive count; the message body was not
  printed. Queue metrics showed zero visible and in-flight messages.
- Reviewed `destroy-reviewed.tfplan` contains zero creates, zero changes, and
  four deletes. Monitored destroy `nova-sns-sqs-449-destroy-nov23a1` started
  at `2026-11-23T14:41:44Z`, supervisor PID 14873, Terraform PID 14874, root
  `/private/tmp/davdeploy-nova-sns-sqs-449-nov23a1`, and log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sns-sqs-449-destroy-nov23a1.log`. It completed at `2026-11-23T14:42:21Z` with zero adds, zero changes, and four destroys. After more than five minutes, AWS listed no exact topic, queue, or subscription. The Terraform state is empty; the run monitor has 27 terminal records and zero active operations.

## Acceptance criteria

- [x] Draft PR and ticket/test evidence precede AWS writes.
- [x] A saved four-resource create plan has no unrelated changes or destroys.
- [x] The exact topic/account queue policy permits the SNS service to deliver.
- [x] One synthetic message arrives with the expected contents; no message body
      is printed in terminal or CI output.
- [x] The received message is deleted and the queue is empty.
- [x] Monitored teardown and independent absence checks pass.
- [x] Required local and PR checks pass.
- [x] No Nova dispatch, hosted execution, or broad customer certification is
      claimed.

## Observed result

One synthetic publish was received exactly once by the subscribed SQS queue.
The body matched the expected JSON, the probe omitted the body from output and
deleted the message. SNS reports one confirmed subscription; the queue reports
zero visible and in-flight messages. This is direct same-account behavior only.

## Teardown

The reviewed exact four-resource destroy succeeded through the PID monitor.
Independent AWS reads after the settling period found the topic, queue, and
subscription absent. Local state is empty and the run monitor has no active
operation.

## Final boundary

The planned test is direct same-account SNS/SQS behavior. It does not establish
Nova dispatch, hosted execution, cross-account isolation, or broad customer
certification. The hosted control plane and production resources are out of
scope.

## Evidence files

- `docs/tickets/ticket449.md`
- `docs/test/test449.md`
- `docs/test/fixtures/nova-sns-sqs-delivery-449/main.tf`
- `docs/test/fixtures/nova-sns-sqs-delivery-449/probe.py`

## Boundaries

Do not touch the hosted control plane, production resources, state/locks,
customer credentials, protected untracked files, or retained audit evidence.
Use the exact test prefix and PID-based Terraform run monitor.
