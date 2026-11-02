# test234 — Delivery module batch

Date: 2026-11-02

Execution type: Real AWS execution in a disposable test account.

Customer repository: None. This was module-level infrastructure validation.

Commit: Final PR commit pending.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

- private S3 artifact bucket with versioning, default encryption and all public
  access blocks enabled;
- immutable, scan-on-push ECR repository;
- least-privilege disposable Lambda execution role and log policy;
- Python 3.12 Lambda function;
- HTTP API, default stage, proxy integration, route and Lambda invoke permission.

## Commands executed

`terraform fmt -recursive ...`

`AWS_PROFILE=ai-platform-pilot-key terraform init -input=false`

`AWS_PROFILE=ai-platform-pilot-key terraform validate`

`AWS_PROFILE=ai-platform-pilot-key terraform apply -auto-approve -input=false -var='test_id=delivery-20261102a'`

`curl --fail-with-body <api-endpoint>/health`

`aws s3api get-public-access-block ...`

`aws ecr describe-repositories ...`

`AWS_PROFILE=ai-platform-pilot-key terraform destroy -auto-approve -input=false -var='test_id=delivery-20261102a'`

## Observed result

The API returned `{"ok":true}`. S3 returned all four public-access blocks as
true. ECR returned immutable tags and scan-on-push as true. Terraform reported
13 resources created and then 13 resources destroyed.

## Teardown

Terraform state was empty after destroy. No test resources were retained.

## Final boundary

All new module entries remain disabled. The CloudFront definition is statically
validated only; its registry state remains disabled pending an origin-specific
real lifecycle validation.
