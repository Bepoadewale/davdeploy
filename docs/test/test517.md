# test517 — Private AWS Batch image and logging path

Date: Planned; no AWS workload execution yet.

Execution type: Not executed; planned direct same-account AWS validation only.

Customer repository: None; disposable DavDeploy test environment.

PR: [#517](https://github.com/Bepoadewale/davdeploy/pull/517).

Commit: Initial test harness commit `ebd0d3e`; update to the exact test commit before any run.

AWS account: `654654474502` (identity must be reverified before any cloud operation).

AWS region: `us-east-1`.

## Resources created

None. Planned resources: one temporary private-only VPC with two private subnets and no internet gateway, NAT gateway, or public IPv4 address; one ECR repository and digest-pinned image; one Batch Fargate compute environment/queue/job definition; two IAM roles; one log group; Batch and endpoint security groups; three interface endpoints (`ecr.api`, `ecr.dkr`, `logs`) across two AZs; and one S3 gateway endpoint on the private route table.

## Commands executed

Read-only preflight only; no Terraform plan/apply or cloud mutation has been executed for this test.

- `AWS_PROFILE=ai-platform-pilot-key aws sts get-caller-identity --query '{Account:Account,Arn:Arn}' --output json` — account `654654474502`, caller `arn:aws:iam::654654474502:user/adewale-terminal`.
- `aws ec2 describe-availability-zones --region us-east-1` — `us-east-1a` and `us-east-1b` are available.
- `aws service-quotas list-service-quotas --service-code fargate --region us-east-1` — Fargate On-Demand vCPU quota is 64; proposed compute ceiling is 1 vCPU.
- `aws resourcegroupstaggingapi get-resources --region us-east-1 --tag-filters Key=Purpose,Values=davdeploy-private-batch-endpoints-517` — no existing tagged test resources.

Current public pricing references reviewed 2026-11-26: AWS PrivateLink lists $0.01 per interface endpoint ENI-hour for the first tier; AWS Fargate lists $0.000011244 per vCPU-second and $0.000001235 per GB-second in us-east-1. At 0.25 vCPU and 0.5 GB, compute is approximately $0.01235/hour before the one-minute minimum. Six endpoint ENIs add approximately $0.06 for the first billed hour. These are preliminary public rates, not a quote; recheck before any apply. Sources: [AWS PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/) and [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/).

## Observed result

Not executed. No image pull, Batch job, or CloudWatch log delivery is claimed.

## Teardown

Not executed. The exact Terraform resources will not be created until the one-hour/USD $1.00 estimated-cost bound, account/region, quota, reviewed plan, and exact cleanup authorization are recorded. If authorized and run, destroy via the PID-based Terraform monitor and verify exact resource absence independently.

## Final boundary

This planned test is direct same-account AWS evidence only. It will not use or modify the hosted control plane and will not prove Nova dispatch, cross-account operation, or broad Batch support.
