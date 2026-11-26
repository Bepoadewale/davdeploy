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

No AWS command or Terraform plan/apply has been executed for this test. Planned commands and exact run IDs will be recorded after a reviewed plan and explicit apply/cleanup authorization.

## Observed result

Not executed. No image pull, Batch job, or CloudWatch log delivery is claimed.

## Teardown

Not executed. The exact Terraform resources will not be created until the one-hour/USD $1.00 estimated-cost bound, account/region, quota, reviewed plan, and exact cleanup authorization are recorded. If authorized and run, destroy via the PID-based Terraform monitor and verify exact resource absence independently.

## Final boundary

This planned test is direct same-account AWS evidence only. It will not use or modify the hosted control plane and will not prove Nova dispatch, cross-account operation, or broad Batch support.
