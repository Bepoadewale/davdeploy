# test517 — Private AWS Batch image and logging path

Date: 2026-11-26.

Execution type: Direct same-account AWS infrastructure validation. The PR #517 stack was provisioned and destroyed. One Batch job was submitted but failed with `JobQueue deleted` while a concurrent cleanup was removing the queue. Private image pull, CloudWatch job-log delivery, and application readiness are not proven.

Customer repository: None; disposable DavDeploy test environment.

PR: [#517](https://github.com/Bepoadewale/davdeploy/pull/517).

Commit: `37b4be1fb330c66bb72791804181d43bcd5bc308`.

This is the tested implementation commit. Final-head CI run `45839400505` passed all seven checks. The cleanup update is documentation-only and does not change the tested implementation.

Exact test ID: `batch-private-endpoints-517-20261126a`.

## Scope and authorization

AWS account: `654654474502`.

AWS region: `us-east-1`.

The hosted control plane and its state/lock resources were not changed. The AWS work used only the exact PR #517 disposable test stack described below. The user explicitly approved cleanup of that exact test scope. No Nova dispatch or customer workload execution is claimed.

The test was originally bounded to one hour and a USD $1.00 estimated-cost ceiling; this estimate is not an AWS billing cap. The actual AWS stack existed from the successful apply at `2026-11-26T14:39:36Z` through destroy completion at `2026-11-26T14:55:00Z` (about 16 minutes). One job was submitted and failed because its queue was deleted during cleanup.

## Resources created

The monitored full apply completed with 22 resources added, one ECR repository tag update, and zero resources destroyed. It created a private VPC with two subnets, a route table and associations, security groups and scoped rules, three interface endpoints (`ecr.api`, `ecr.dkr`, `logs`), an S3 gateway endpoint, an AWS Batch Fargate compute environment, queue and job definition, a task execution role and attachment, a CloudWatch log group, and the Batch service-linked role. The existing test ECR repository received an expiry-tag update.

The ECR repository contained these five exact manifests before cleanup:

- `sha256:6a5669825cfe72b4b87fb29bf9e813fdcceac14613e8b4cb9e60713343ca4b35`
- `sha256:9e0fc38dcaa34bddbf825f9f26fd216bb091221318a1c4a677e7e93e8af2863f`
- `sha256:0255782e783c64793bc082d327bfed55aaca468ff85dc52de9e73c19f15af609`
- `sha256:2ecf897431368650ff88989150358f12375f83459849e46d787fc8b66eb8daf2` (tag `20261126a`)
- `sha256:e7265ccc6387caa80d69aa215049baddb204e6736eb49623b9afc1fdbc49013d` (tag `run-20261126a`)

The last tagged digest was a duplicate produced by a second image build. All five digests were explicitly removed before Terraform deleted the repository.

## Commands executed

- `AWS_PROFILE=ai-platform-pilot-key python3 scripts/terraform_run_monitor.py start apply infrastructure/terraform/module-validation/batch-private-endpoints --run-id batch-private-517-full-apply-20261126b --terraform-arg=/private/tmp/davdeploy-batch-private-endpoints-517-20261126a/full-v3.tfplan` — succeeded; 22 added, one changed, zero destroyed.
- `AWS_PROFILE=ai-platform-pilot-key aws ecr batch-delete-image --region us-east-1 --repository-name davdeploy-batch-private-endpoints-517-20261126a --image-ids <the five exact imageDigest values listed above>` — all five deleted, no failures.
- `AWS_PROFILE=ai-platform-pilot-key python3 scripts/terraform_run_monitor.py start destroy infrastructure/terraform/module-validation/batch-private-endpoints --run-id nova-batch517-cleanup-approved-20261126 --terraform-arg=/private/tmp/davdeploy-batch-private-endpoints-517-20261126a/destroy-approved.tfplan` — Terraform rejected the command before changes because a saved destroy plan must be applied with `terraform apply`.
- `AWS_PROFILE=ai-platform-pilot-key python3 scripts/terraform_run_monitor.py start apply infrastructure/terraform/module-validation/batch-private-endpoints --run-id nova-batch517-cleanup-approved-apply-20261126 --terraform-arg=/private/tmp/davdeploy-batch-private-endpoints-517-20261126a/destroy-approved.tfplan` — succeeded; 0 added, 0 changed, 23 destroyed.
- `AWS_PROFILE=ai-platform-pilot-key aws batch submit-job --region us-east-1 --job-name davdeploy-private-batch-517-20261126a --job-queue davdeploy-batch-private-endpoints-517-20261126a --job-definition davdeploy-batch-private-endpoints-517-20261126a` — submitted job `3d1b3de1-0e7b-4a7f-8605-bb7f37777f2d`. It entered `STARTING` and then failed with status reason `JobQueue deleted`.
- A concurrent monitored cleanup run `nova-batch517-cleanup-approved-apply-20261126` deleted the queue during the job startup. AWS CloudTrail records the exact `DeleteJobQueue` event under the expected account user at `2026-11-26T14:53:02+01:00`; no replacement job was submitted. The image pull and CloudWatch log path therefore remain unproven.
- Independent AWS service-specific `describe` calls checked the exact VPC, subnets, route table, VPC endpoint IDs, security groups/rules, Batch environment and queue, ECR repository, log group, task role, service-linked role, and inactive job definition.

## Apply and cleanup evidence

- The first full-plan apply, `batch-private-517-full-apply-20261126a`, failed before creating stack resources because `AWS_PROFILE` was not inherited.
- A subsequent full apply, `batch-private-517-full-apply-20261126b`, succeeded through `scripts/terraform_run_monitor.py` in account `654654474502`, region `us-east-1`, at `2026-11-26T14:40:59Z`. The monitor log is `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/batch-private-517-full-apply-20261126b.log`. Terraform reported 22 added, one changed, and zero destroyed.
- The ECR deletion request named exactly the five digests above and returned five deleted image IDs with no failures.
- Reviewed destroy plan: `/private/tmp/davdeploy-batch-private-endpoints-517-20261126a/destroy-approved.tfplan`. It contained exactly 23 deletes, zero adds, and zero changes. The 23 addresses were the test VPC/network/endpoints/security groups, Batch compute environment/queue/job definition, ECR repository, task role and attachment, CloudWatch log group, and the test-created `AWSServiceRoleForBatch` service-linked role.
- The first monitored invocation used `terraform destroy <saved-plan>` and Terraform rejected it before making changes. The same saved destroy plan was then correctly executed with monitored `terraform apply <saved-plan>`: run ID `nova-batch517-cleanup-approved-apply-20261126`, supervisor PID `11815`, Terraform PID `11816`, exit code `0`. The monitor log is `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-batch517-cleanup-approved-apply-20261126.log`. Terraform reported 0 added, 0 changed, 23 destroyed.
- Independent checks in the same verified AWS account found the ECR repository absent; VPC, subnets, route table, four VPC endpoints, security groups and three security-group rules absent; Batch compute environment and queue absent; CloudWatch log group absent; task execution role and `AWSServiceRoleForBatch` absent. The Terraform state contains no managed resources and the run monitor has no active Terraform operations.
- AWS Batch retains the test job definition as inactive history: `arn:aws:batch:us-east-1:654654474502:job-definition/davdeploy-batch-private-endpoints-517-20261126a:1`. This is not an active workload and was preserved as audit evidence.
- At the time of the independent checks, the Resource Groups Tagging API still returned stale ARN entries for the four deleted VPC endpoints and three deleted security-group rules, despite their service-specific Describe APIs returning not-found/empty results. Its response also listed the retained inactive Batch job definition. Treat those tag-index entries as a reconciliation caveat; the direct service APIs verified the live resources absent.

## Observed result

One Batch job was submitted, but it failed with `JobQueue deleted` during the concurrent Terraform cleanup. No claim is made that Fargate reached the image, downloaded it privately, started the container, sent CloudWatch logs, or reached application readiness. This run proves infrastructure provisioning and cleanup only.

## Teardown

The user approved cleanup of this exact test environment. All five ECR image digests were deleted, then the reviewed 23-resource Terraform destroy plan succeeded through the PID-based monitor. Independent service-specific AWS APIs verified the live resources absent. The inactive Batch job-definition record remains under AWS retention, and the Resource Groups Tagging API returned stale endpoint/rule ARNs at verification time; see the cleanup evidence above.

## Local clean-room validation

In an isolated worktree using Compose project `davdeploy-pr517-cleanroom`, ran bootstrap, smoke, API contract, customer-plan E2E, the five canonical demos, seed/restart persistence, trace checks, and `make verify`. Result: 1,971 tests passed with one upstream Starlette/httpx deprecation warning. This used local fixtures only and is not AWS workload evidence. Project containers were removed. The project Postgres volume `davdeploy-pr517-cleanroom_davdeploy-postgres`, local `.venv/`, and `.local/` remain untouched.

## Limits

This is direct same-account AWS infrastructure evidence. It does not prove a successful private Batch job, private ECR pull, CloudWatch job-log delivery, Nova dispatch, cross-account operation, all Batch images, general private internet egress, or any other workload family. The inactive job definition is retained by AWS; the Resource Groups Tagging API had stale entries as recorded above. The hosted control plane remained untouched.

## Final boundary

The hosted control plane and its state/lock resources were not changed. The evidence is limited to this disposable same-account AWS infrastructure apply and cleanup; no workload execution or Nova dispatch is claimed.

## Retry cycle b — exact manifest before apply

This separate retry uses test ID `batch-private-endpoints-517-20261126b` and
ECR repository `davdeploy-batch-private-endpoints-517-20261126b` in account
`654654474502`, region `us-east-1`. Its `ExpiresAt` tag is
`2026-11-26T17:15:00Z`; the maximum runtime is one hour. Fresh preflight at
2026-11-26 confirmed the expected account, no AWS resources tagged with this
TestId, no repository with this name, no `AWSServiceRoleForBatch`, no Batch
compute environment in `us-east-1`, an empty Terraform test state, and no
active monitored Terraform operation. The exact prior stack-a resources are
absent; the retained inactive job definition belongs only to suffix `a`.

The authorized manifest is limited to one ECR repository and one immutable
Linux/x86 test image; one private two-AZ VPC with two private subnets and no
internet gateway, NAT, or public IPv4; one route table and associations; two
security groups and three scoped security-group rules; three interface
endpoints (`ecr.api`, `ecr.dkr`, `logs`) across the two AZs; one S3 gateway
endpoint; one CloudWatch log group; one ECS task execution role and policy
attachment; one explicitly owned AWS Batch service-linked role; and one Batch
Fargate compute environment, queue, and job definition capped at one vCPU. One
job will be submitted once with a five-minute timeout. It must reach
`SUCCEEDED`; the exact digest-pinned image and CloudWatch stream must be
verified before teardown.

The estimated fixed charges remain approximately $0.0724 for one endpoint
hour plus one hour of 0.25-vCPU/0.5-GiB Fargate, before data processing,
logging, and ECR storage. The estimated spend is bounded at $1.00 by prompt
cleanup; this is not an AWS billing cap. The test has not started: no ECR
repository, image, VPC, endpoint, IAM role, Batch environment, queue, or log
group exists for suffix `b`. Generate the targeted ECR plan and full saved
plan in a private `0700` artifact directory with plans/logs mode `0600`,
review their exact resources and actions, then apply through the Terraform
monitor. Destroy only the exact suffix-`b` state and image digests, then
independently verify resource absence. No control-plane resource or retained
suffix-`a` audit history is in this retry's cleanup scope.
