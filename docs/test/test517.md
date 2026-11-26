# test517 — Private AWS Batch image and logging path

Date: 2026-11-26.

Execution type: Direct same-account AWS validation. The targeted ECR bootstrap
was applied and one test image was pushed; the workload plan has not been
applied.

Customer repository: None; disposable DavDeploy test environment.

PR: [#517](https://github.com/Bepoadewale/davdeploy/pull/517).

Commit: PR head at last completed CI `9a44de28c31ce6a398d3cb3ac5a3efa363a4c4dc`; current uncommitted implementation changes require a new final-head CI run.

Exact test ID: `batch-private-endpoints-517-20261126a`.

Expiry tag: `2026-11-26T09:45:00Z`; maximum environment lifetime is one hour.

## Authorization and plan review

The user authorized disposable AWS validation resources identified by an exact
manifest and test ID. This run is restricted to this test ID and account
`654654474502`; no existing or production resources are targets. The first
saved plan is an intentionally targeted bootstrap plan that creates exactly
`module.ecr.aws_ecr_repository.this` (`davdeploy-batch-private-endpoints-517-20261126a`).
Terraform reports one create, zero updates and zero deletes; it is applyable,
not errored. It is stored at
`/private/tmp/davdeploy-batch-private-endpoints-517-20261126a/ecr.tfplan`
(mode 600), with its log beside it (mode 600). This targeted plan is only for
the ECR bootstrap; a separate complete saved plan will cover the workload.

The user has authorized cleanup of the exact disposable resources under this
manifest. Cleanup will delete only the image digest pushed to the named test
repository, then destroy the resources in this test's local Terraform state
through the run monitor. The independent absence check will be scoped to the
exact test ID/name/ARN set; no general account-wide deletion is permitted.

Fresh preflight on 2026-11-26 confirmed account `654654474502`, available
`us-east-1a` and `us-east-1b`, a 64-vCPU Fargate On-Demand quota versus this
test's 1-vCPU ceiling, no resource tagged with this exact `TestId`, and no
existing ECR repository with the exact test name. Public AWS rates reviewed
for this run are $0.01 per interface endpoint ENI-hour and $0.000011244 per
vCPU-second plus $0.000001235 per GB-second for Linux/x86 Fargate in
us-east-1. Six endpoint ENI-hours plus a 0.25-vCPU/0.5-GB one-hour job are
about $0.0724 before endpoint data, logs, and small ECR storage. The total
estimate is bounded to $1.00 over at most one hour; this is not an AWS billing
cap. Recheck prices and quota before the full-plan apply.

AWS account: `654654474502` (identity must be reverified before any cloud operation).

AWS region: `us-east-1`.

## Resources created

Created: ECR repository `davdeploy-batch-private-endpoints-517-20261126a`
and one test image. Remaining planned resources: one temporary private-only
VPC with two private subnets and no internet gateway, NAT gateway, or public
IPv4 address; one Batch Fargate compute environment, queue, and job definition;
the account-level, untaggable `AWSServiceRoleForBatch` service-linked role at
Terraform address `aws_iam_service_linked_role.batch`; one task execution role;
one log group; Batch and endpoint security groups; three interface endpoints
(`ecr.api`, `ecr.dkr`, `logs`) across two AZs; and one S3 gateway endpoint on
the private route table. The role was absent before the test. A preflight found
no Batch compute environments in 17 enabled regions; recheck globally before
removing the exact role during teardown.

## Commands executed

The ECR bootstrap plan was created and applied; the image was pushed. No VPC,
endpoint, Batch, or log-group resources have been applied.

- `AWS_PROFILE=ai-platform-pilot-key aws sts get-caller-identity --query '{Account:Account,Arn:Arn}' --output json` — account `654654474502`, caller `arn:aws:iam::654654474502:user/adewale-terminal`.
- `aws ec2 describe-availability-zones --region us-east-1` — `us-east-1a` and `us-east-1b` are available.
- `aws service-quotas list-service-quotas --service-code fargate --region us-east-1` — Fargate On-Demand vCPU quota is 64; proposed compute ceiling is 1 vCPU.
- `aws resourcegroupstaggingapi get-resources --region us-east-1 --tag-filters Key=Purpose,Values=davdeploy-private-batch-endpoints-517` — no existing tagged test resources.
- `aws resourcegroupstaggingapi get-resources --region us-east-1 --tag-filters Key=TestId,Values=batch-private-endpoints-517-20261126a` — no resource has this exact test ID.
- `terraform plan -target=module.ecr ... -out=ecr.tfplan` — exact result: one `aws_ecr_repository` create, zero updates/deletes; plan is applyable and saved mode 600. The initial invocation without `AWS_PROFILE` failed with no credentials and made no changes; the profile-scoped retry succeeded.
- `AWS_PROFILE=ai-platform-pilot-key python3 scripts/terraform_run_monitor.py start apply infrastructure/terraform/module-validation/batch-private-endpoints --run-id nova-batch517-ecr-apply-20261126a --terraform-arg=/private/tmp/davdeploy-batch-private-endpoints-517-20261126a/ecr.tfplan` — succeeded, supervisor PID `92773`, Terraform PID `92774`; monitor log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-batch517-ecr-apply-20261126a.log`.
- `docker build --platform linux/amd64 --tag davdeploy-private-batch-endpoints-517:20261126a infrastructure/terraform/module-validation/batch-private-endpoints/image` and `docker push --quiet 654654474502.dkr.ecr.us-east-1.amazonaws.com/davdeploy-batch-private-endpoints-517-20261126a:20261126a` — succeeded. Registry digest `sha256:2ecf897431368650ff88989150358f12375f83459849e46d787fc8b66eb8daf2`, size 54,566,047 bytes.
- AWS Batch service-linked-role preflight — `AWSServiceRoleForBatch` was absent and `describe-compute-environments` found none in 17 enabled regions. This exact, untaggable role is declared as `aws_iam_service_linked_role.batch` for owned cleanup.

Current public pricing references reviewed 2026-11-26: AWS PrivateLink lists $0.01 per interface endpoint ENI-hour for the first tier; AWS Fargate lists $0.000011244 per vCPU-second and $0.000001235 per GB-second in us-east-1. At 0.25 vCPU and 0.5 GB, compute is approximately $0.01235/hour before the one-minute minimum. Six endpoint ENIs add approximately $0.06 for the first billed hour. These are preliminary public rates, not a quote; recheck before any apply. Sources: [AWS PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/) and [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/).

## Observed result

The ECR repository and test image exist from the bootstrap phase. The full
network/Batch plan has not been applied. No private image pull, Batch job, or
CloudWatch log delivery is claimed.

## Local clean-room validation

In a fresh worktree using isolated Compose project `davdeploy-pr517-cleanroom`, ran `make bootstrap-local`, then the repository's smoke, API contract, customer plan E2E, simple/complex/degraded/Day-2/failure/readiness-failure demos, seed and API-restart persistence check, trace check, and `make verify`. Result: passed; `make verify` reported 1,971 tests passed with one upstream Starlette/httpx deprecation warning. This used local fixtures only and is not AWS workload evidence. Project containers were stopped and removed. The project Postgres volume `davdeploy-pr517-cleanroom_davdeploy-postgres`, local `.venv/`, and `.local/` remain untouched pending explicit cleanup approval.

## Teardown

Not executed. The exact Terraform resources will not be created until the one-hour/USD $1.00 estimated-cost bound, account/region, quota, reviewed plan, and exact cleanup authorization are recorded. If authorized and run, destroy via the PID-based Terraform monitor and verify exact resource absence independently.

## Final boundary

This planned test is direct same-account AWS evidence only. It will not use or modify the hosted control plane and will not prove Nova dispatch, cross-account operation, or broad Batch support.
