# test237 — AI module batch

Date: 2026-11-02

Execution type: Focused disposable Kinesis validation and static module
validation for the remaining AI/data-processing modules.

Customer repository: None.

Commit: Pending final batch commit.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

- a one-shard Kinesis stream encrypted with the AWS managed Kinesis key.

## Commands executed

`terraform fmt -recursive infrastructure/terraform/modules/{bedrock-runtime,bedrock-knowledge-base,sagemaker-endpoint,kinesis-stream,batch-compute}`

`AWS_PROFILE=ai-platform-pilot-key terraform init -input=false`

`AWS_PROFILE=ai-platform-pilot-key terraform validate`

`AWS_PROFILE=ai-platform-pilot-key terraform apply -auto-approve -input=false -var='test_id=ai-20261102a'`

## Observed result

Kinesis lifecycle and teardown evidence are updated after the active test
finishes. Bedrock, knowledge-base, SageMaker and Batch modules remain disabled
until their workload-specific prerequisites and controls are validated.

## Teardown

The disposable Kinesis test root destroys the stream before review readiness.

## Final boundary

All new module entries remain disabled.
