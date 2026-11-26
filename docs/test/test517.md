# test517 — Private AWS Batch image and logging path

Date: 2026-11-26.

Execution type: Direct same-account AWS validation. The targeted ECR bootstrap
was applied and one test image was pushed; the workload plan has not been
applied.

Customer repository: None; disposable DavDeploy test environment.

PR: [#517](https://github.com/Bepoadewale/davdeploy/pull/517).

Commit: `94088574ed4cee18e598acb891ead564d0a90572`. Final-head CI run
`45789356920` is in progress.

Exact test ID: `batch-private-endpoints-517-20261126a`.

Original expiry tag: `2026-11-26T09:45:00Z`. The latest reviewed plan changes
it to `2026-11-26T11:00:00Z`; the maximum environment runtime remains one hour.

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

The active Nova goal authorizes creation and teardown of disposable AWS
validation resources identified by exact manifests and test IDs. This test's
scope is limited to this exact TestId, repository, image digests, resource
names/ARNs, and its Terraform state; no control-plane or account-wide cleanup
is authorized. The exact image and resource inventory is recorded below and
must be rechecked before teardown.

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

Created: ECR repository `davdeploy-batch-private-endpoints-517-20261126a` and
two tagged test image manifests, one intended and one duplicate. ECR reports
these five exact image digests in the repository (three are untagged OCI
attestation/layer manifests): `sha256:6a5669825cfe72b4b87fb29bf9e813fdcceac14613e8b4cb9e60713343ca4b35`,
`sha256:9e0fc38dcaa34bddbf825f9f26fd216bb091221318a1c4a677e7e93e8af2863f`,
`sha256:0255782e783c64793bc082d327bfed55aaca468ff85dc52de9e73c19f15af609`,
`sha256:2ecf897431368650ff88989150358f12375f83459849e46d787fc8b66eb8daf2`
(tag `20261126a`), and
`sha256:e7265ccc6387caa80d69aa215049baddb204e6736eb49623b9afc1fdbc49013d`
(tag `run-20261126a`). The final plan should use the first tagged image
(`2ecf…`); the second tagged image is an accidental duplicate from rebuilding
and pushing the same test image.

Remaining planned resources: one temporary private-only
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

The ECR bootstrap plan was created and applied; a test image was pushed. A
full-plan apply attempt failed before any resource creation because the
Terraform monitor process lacked `AWS_PROFILE`; the monitor confirms exit code
1 and the state contains only the ECR repository. No VPC, endpoint, Batch, or
log-group resources were applied.

- `AWS_PROFILE=ai-platform-pilot-key aws sts get-caller-identity --query '{Account:Account,Arn:Arn}' --output json` — account `654654474502`, caller `arn:aws:iam::654654474502:user/adewale-terminal`.
- `aws ec2 describe-availability-zones --region us-east-1` — `us-east-1a` and `us-east-1b` are available.
- `aws service-quotas list-service-quotas --service-code fargate --region us-east-1` — Fargate On-Demand vCPU quota is 64; proposed compute ceiling is 1 vCPU.
- `aws resourcegroupstaggingapi get-resources --region us-east-1 --tag-filters Key=Purpose,Values=davdeploy-private-batch-endpoints-517` — no existing tagged test resources.
- `aws resourcegroupstaggingapi get-resources --region us-east-1 --tag-filters Key=TestId,Values=batch-private-endpoints-517-20261126a` — no resource has this exact test ID.
- `terraform plan -target=module.ecr ... -out=ecr.tfplan` — exact result: one `aws_ecr_repository` create, zero updates/deletes; plan is applyable and saved mode 600. The initial invocation without `AWS_PROFILE` failed with no credentials and made no changes; the profile-scoped retry succeeded.
- `AWS_PROFILE=ai-platform-pilot-key python3 scripts/terraform_run_monitor.py start apply infrastructure/terraform/module-validation/batch-private-endpoints --run-id nova-batch517-ecr-apply-20261126a --terraform-arg=/private/tmp/davdeploy-batch-private-endpoints-517-20261126a/ecr.tfplan` — succeeded, supervisor PID `92773`, Terraform PID `92774`; monitor log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-batch517-ecr-apply-20261126a.log`.
- `docker buildx build --platform linux/amd64 --load --tag davdeploy-batch-private-endpoints-517:run-20261126a infrastructure/terraform/module-validation/batch-private-endpoints/image`, local `docker run`, and ECR push to tag `run-20261126a` — succeeded, but duplicated the existing test image. Tagged digest `sha256:e7265ccc6387caa80d69aa215049baddb204e6736eb49623b9afc1fdbc49013d`. ECR also lists three untagged manifests; all five digests are enumerated above. No image has been deleted.
- AWS Batch service-linked-role preflight — `AWSServiceRoleForBatch` was absent and `describe-compute-environments` found none in 17 enabled regions. This exact, untaggable role is declared as `aws_iam_service_linked_role.batch` for owned cleanup.
- Monitored full-plan attempt `batch-private-517-full-apply-20261126a` failed at 08:55:35Z due missing credentials before creating resources; log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/batch-private-517-full-apply-20261126a.log`.
- Latest read-only saved plan `/tmp/davdeploy-batch-private-517-final-reviewed.tfplan`: 22 creates, one ECR expiry-tag update, zero deletes. It references the intended digest `sha256:2ecf897431368650ff88989150358f12375f83459849e46d787fc8b66eb8daf2`. Cleanup approval for this AWS scope is pending.
- Current ECR inventory contains the five exact digests listed above. No image has been deleted.

Current public pricing references reviewed 2026-11-26: AWS PrivateLink lists $0.01 per interface endpoint ENI-hour for the first tier; AWS Fargate lists $0.000011244 per vCPU-second and $0.000001235 per GB-second in us-east-1. At 0.25 vCPU and 0.5 GB, compute is approximately $0.01235/hour before the one-minute minimum. Six endpoint ENIs add approximately $0.06 for the first billed hour. These are preliminary public rates, not a quote; recheck before any apply. Sources: [AWS PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/) and [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/).

## Observed result

The ECR repository and two tagged test image manifests exist. The full
network/Batch plan has not been applied. No private image pull, Batch job, or
CloudWatch log delivery is claimed.

## Local clean-room validation

In a fresh worktree using isolated Compose project `davdeploy-pr517-cleanroom`, ran `make bootstrap-local`, then the repository's smoke, API contract, customer plan E2E, simple/complex/degraded/Day-2/failure/readiness-failure demos, seed and API-restart persistence check, trace check, and `make verify`. Result: passed; `make verify` reported 1,971 tests passed with one upstream Starlette/httpx deprecation warning. This used local fixtures only and is not AWS workload evidence. Project containers were stopped and removed. The project Postgres volume `davdeploy-pr517-cleanroom_davdeploy-postgres`, local `.venv/`, and `.local/` remain untouched pending explicit cleanup approval.

## Teardown

Not executed. Under the active goal's exact-manifest authorization, delete only
the five image digests listed above, destroy only this test's Terraform state
through the PID-based monitor, independently verify absence, and record
AWS-retained Batch job-definition and service-linked-role lifecycle. Recheck
the exact current inventory immediately before starting teardown.

## Final boundary

This planned test is direct same-account AWS evidence only. It will not use or modify the hosted control plane and will not prove Nova dispatch, cross-account operation, or broad Batch support.
