# test235 — Data module batch

Date: 2026-11-02

Execution type: Focused real AWS disposable DynamoDB validation and static
validation of private data-service modules.

Customer repository: None.

Commit: Final PR commit pending.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

- a disposable DynamoDB on-demand table with server-side encryption and point
  in time recovery enabled.

## Commands executed

`terraform fmt -recursive infrastructure/terraform/modules/{dynamodb-table,aurora-postgres,elasticache-redis,opensearch,efs-shared-storage}`

`AWS_PROFILE=ai-platform-pilot-key terraform init -input=false`

`AWS_PROFILE=ai-platform-pilot-key terraform validate`

`AWS_PROFILE=ai-platform-pilot-key terraform apply -auto-approve -input=false -var='test_id=data-20261102b'`

`AWS_PROFILE=ai-platform-pilot-key terraform destroy -auto-approve -input=false -var='test_id=data-20261102b'`

## Observed result

The DynamoDB lifecycle result and teardown are recorded after the running
controlled test finishes. Aurora PostgreSQL, Redis, OpenSearch and EFS are
only statically validated in this PR, because they require a VPC plus service
specific availability, recovery and cost validation.

## Teardown

The DynamoDB test root destroys all resources. No customer resources are
created by this PR.

## Final boundary

All new module entries remain disabled. A valid Terraform module is not an
authorisation to deploy a customer data service.
