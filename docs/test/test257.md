# test257 — Real EventBridge to SQS workload certification

Date: 2026-11-03

Execution type: Controlled disposable AWS workload validation.

Customer repository: None.

Commit: `5acda65` plus evidence update in progress.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

Disposable EventBridge bus/rule/target, encrypted SQS queue and DLQ, SNS topic,
and a queue policy restricted to the exact rule ARN.

## Commands executed

Terraform monitor applied and destroyed the root. `aws events put-events` sent
one event; `aws sqs receive-message` read the delivered body.

## Observed result

Event `bb3bbe2b-ecc6-bd36-a98a-393e623d4873` was accepted and its exact source,
detail type and JSON detail arrived in SQS.

## Teardown

Terraform recorded `Destroy complete! Resources: 7 destroyed.`

## Final boundary

This certifies delivery only, not a consumer, replay or DLQ transition.
