# test449 — isolated SNS-to-SQS delivery

Date: 2026-11-23

Execution type: Controlled disposable AWS workload validation.

Customer repository: None; direct same-account AWS service test.

Commit: Pending fixture commit.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The test plans one SNS topic, one SQS queue, one SQS queue policy, and one SNS
subscription under the unique `davdeploy-nova-sns-sqs-449-nov23a1` prefix.
Terraform state and generated files stay outside the repository. The stack
will be created only after the draft PR and exact create plan are reviewed.

## Commands executed

Pending controlled execution after the draft PR is open and the create plan has
been reviewed.

## Acceptance criteria

- [ ] Draft PR and ticket/test evidence precede AWS writes.
- [ ] A saved four-resource create plan has no unrelated changes or destroys.
- [ ] The exact topic/account queue policy permits the SNS service to deliver.
- [ ] One synthetic message arrives with the expected contents; no message body
      is printed in terminal or CI output.
- [ ] The received message is deleted and the queue is empty.
- [ ] Monitored teardown and independent absence checks pass.
- [ ] Required local and PR checks pass.
- [ ] No Nova dispatch, hosted execution, or broad customer certification is
      claimed.

## Observed result

Pending controlled execution.

## Teardown

Pending monitored destroy and independent AWS absence checks.

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
