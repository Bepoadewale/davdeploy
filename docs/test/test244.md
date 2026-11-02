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
- OpenSearch domain in the default VPC, with encryption at rest, node-to-node
  encryption and an enforced HTTPS endpoint.
- Step Functions STANDARD state machine with a disposable execution role.
- EC2 launch template and zero-capacity Auto Scaling group using the current
  Amazon Linux 2023 SSM public AMI parameter.
- Route 53 hosted zone, primary/secondary CNAME failover records and an HTTPS
  health check in an intentionally non-delegated `.invalid` validation zone.
- AWS Batch Fargate compute environment, queue and job definition with
  disposable service and task-execution roles.
- A disposable private VPC, NAT gateway, EKS 1.31 private-endpoint cluster,
  OIDC provider and two-node managed node group.
- A site-to-site VPN object graph using a TEST-NET-2 peer. It intentionally
  proved resource lifecycle only, not tunnel connectivity.

## Commands executed

`terraform apply` / `terraform destroy` in `module-validation/data`, `ai`,
`bedrock`, `data-services`, `cloudfront`, `opensearch`, `workflow`,
`ec2-autoscaling`, `dns-failover`, `batch`, `eks` and `vpn`, under
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

OpenSearch reached its completed, non-processing state before destruction.
Step Functions, Auto Scaling and Batch each reached their service-valid
ready state. The Batch compute environment reported `VALID` and `ENABLED`;
the queue also reported `VALID` and `ENABLED`. The Route 53 validation zone
was deliberately not delegated, so this proves AWS failover-record lifecycle,
not public DNS propagation. The EKS cluster reached `ACTIVE` with the private
endpoint enabled, and its managed node group reached `ACTIVE` with two
`t3.medium` nodes. The VPC, subnets, routes, Internet gateway and NAT gateway
were created as its network boundary. The VPN connection was created with
both tunnels DOWN as expected for the documentation-only peer, then was
destroyed.

The remaining modules have strict, concrete prerequisites that cannot be
truthfully replaced by a disposable synthetic test: ACM and SES require a
domain owner to publish validation DNS records; Bedrock Knowledge Bases need
an OpenSearch Serverless collection, data-access policies, a vector index and
a least-privilege service role; SageMaker needs a model artifact or verified
serving image plus a scoped execution role. No module has been enabled on the
basis of an incomplete prerequisite test.

## Teardown

Every completed lifecycle test was destroyed. Terraform state was empty in
each root after teardown. Direct AWS describe calls confirmed that the final
VPN, Batch job definition and NAT gateway were deleted. The Resource Groups
Tagging API can retain a short-lived stale result after deletion, so it is not
used as the sole absence check.

## Final boundary

Modules remain disabled until their specific validation, policy and lifecycle
requirements are satisfied.

## Repository verification

- `make test`: 330 passed, one pre-existing Starlette/httpx deprecation
  warning.
- `python scripts/check_doc_conventions.py`: passed.
- `make terraform-validate`: passed after the Batch queue was updated from the
  deprecated `compute_environments` argument to
  `compute_environment_order`.
