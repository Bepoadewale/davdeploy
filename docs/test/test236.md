# test236 — Events module batch

Date: 2026-11-02

Execution type: Focused disposable AWS event-service validation.

Customer repository: None.

Commit: Final PR commit pending.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

- disposable SQS queue and DLQ with SQS managed encryption;
- disposable EventBridge bus;
- disposable SNS topic encrypted with the AWS managed SNS key.

## Commands executed

`terraform fmt -recursive infrastructure/terraform/modules/{sqs-queue,eventbridge-bus,step-functions,sns-notifications,ses-email}`

`AWS_PROFILE=ai-platform-pilot-key terraform init -input=false`

`AWS_PROFILE=ai-platform-pilot-key terraform validate`

`AWS_PROFILE=ai-platform-pilot-key terraform apply -auto-approve -input=false -var='test_id=events-20261102a'`

## Observed result

The controlled apply has created the EventBridge bus, SNS topic and queue pair.
SES is only defined: it requires a domain owner to publish DNS records. Step
Functions requires a workflow-specific execution role. Teardown/state evidence
will be updated after the active Terraform process finishes.

## Teardown

The test root destroys all disposable resources before review readiness.

## Final boundary

All new module entries remain disabled.
