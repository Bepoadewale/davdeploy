# test244 — Complete controlled module lifecycle validation

Date: 2026-11-02

Execution type: Real AWS disposable validation and static prerequisite review.

Customer repository: None.

Commit: In progress.

AWS account: `654654474502`.

AWS region: `us-east-1` unless a test records otherwise.

## Resources created

- DynamoDB table with point-in-time recovery and server-side encryption;
- Kinesis stream encrypted with the AWS managed Kinesis key;
- Bedrock guardrail with a HATE content-policy filter;
- Aurora PostgreSQL Serverless v2 cluster and writer, ElastiCache Redis
  replication group, EFS file system/mount targets, and their private security
  groups in the disposable default-VPC test boundary.
- CloudFront distribution with HTTPS-only custom origin, HTTPS redirect and
  the default CloudFront certificate.

## Commands executed

`terraform apply` / `terraform destroy` in `module-validation/data`, `ai`,
`bedrock`, `data-services` and `cloudfront`, under
`AWS_PROFILE=ai-platform-pilot-key`.

## Observed result

An orphaned Kinesis test stream from an interrupted earlier run was found and
deleted before new validation began. DynamoDB verified point-in-time recovery
and SSE; Kinesis reached ACTIVE with KMS encryption; the Bedrock guardrail
reached READY. The first guardrail attempt exposed a provider-valid but AWS
invalid configuration: at least one policy is mandatory. A content policy was
added and the next lifecycle completed. The data-services run exposed
apply-time `for_each` keys derived from an unknown security-group ID. Modules
now use stable list-index keys, then Aurora, Redis and EFS all reached
available before teardown.

CloudFront deployed successfully with `www.example.com` as an intentionally
non-customer test origin. Its generated distribution endpoint returned an
expected origin 404 for `/index.html`, proving the edge path reached the
origin; the distribution was then deleted.

## Teardown

Every listed resource was destroyed. Terraform state and the tagged-resource
query were empty after the data-services teardown.

## Final boundary

Modules remain disabled until their specific validation, policy and lifecycle
requirements are satisfied.
