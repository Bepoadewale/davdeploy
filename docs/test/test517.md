# test517 — Private AWS Batch image and logging path

Date: 2026-11-26.

Execution type: Direct same-account AWS validation. Two isolated PR #517 test cycles were provisioned and destroyed. Suffix `a` had a Batch job fail with `JobQueue deleted` during cleanup. Suffix `b` ran one Batch job to `SUCCEEDED` with exit code 0, verified the digest-pinned private ECR image and CloudWatch log output, and was then destroyed. No Nova dispatch or general customer workload certification is claimed.

Customer repository: None; disposable DavDeploy test environment.

PR: [#517](https://github.com/Bepoadewale/davdeploy/pull/517).

Commit: `37b4be1fb330c66bb72791804181d43bcd5bc308`.

This is the tested implementation commit. Final-head CI run `45839400505` passed all seven checks. Documentation head `348b42183f326cf09814941c66ab638bec3321a9` also passed all seven checks in run `45857313067`; later lifecycle evidence changes are documentation-only.

Exact test ID: `batch-private-endpoints-517-20261126a`.

## Scope and authorization

AWS account: `654654474502`.

AWS region: `us-east-1`.

The hosted control plane and its state/lock resources were not changed. Both AWS cycles used separate exact PR #517 test IDs and isolated Terraform state. Cleanup was limited to those test manifests. No Nova dispatch or customer workload execution is claimed.

Each cycle was bounded to one hour and an estimated USD $1.00 maximum; this is not an AWS billing cap. Suffix `a` existed from `2026-11-26T14:39:36Z` to `14:55:00Z`. Suffix `b`'s ECR repository was created at `16:22:22Z`, its full stack completed at `16:34:20Z`, and teardown completed at `16:45:23Z`. Suffix `a`'s job failed during queue deletion; suffix `b`'s single job succeeded and was stopped before teardown.

## Resources created

The monitored full apply completed with 22 resources added, one ECR repository tag update, and zero resources destroyed. It created a private VPC with two subnets, a route table and associations, security groups and scoped rules, three interface endpoints (`ecr.api`, `ecr.dkr`, `logs`), an S3 gateway endpoint, an AWS Batch Fargate compute environment, queue and job definition, a task execution role and attachment, a CloudWatch log group, and the Batch service-linked role. The existing test ECR repository received an expiry-tag update.

The ECR repository contained these five exact manifests before cleanup:

- `sha256:6a5669825cfe72b4b87fb29bf9e813fdcceac14613e8b4cb9e60713343ca4b35`
- `sha256:9e0fc38dcaa34bddbf825f9f26fd216bb091221318a1c4a677e7e93e8af2863f`
- `sha256:0255782e783c64793bc082d327bfed55aaca468ff85dc52de9e73c19f15af609`
- `sha256:2ecf897431368650ff88989150358f12375f83459849e46d787fc8b66eb8daf2` (tag `20261126a`)
- `sha256:e7265ccc6387caa80d69aa215049baddb204e6736eb49623b9afc1fdbc49013d` (tag `run-20261126a`)

The last tagged digest was a duplicate produced by a second image build. All five digests were explicitly removed before Terraform deleted the repository.

Suffix `b` used the checked-in echo-container behavior. Its immutable tag
`20261126b` resolved to
`sha256:fa6dd10e24e4401dca9523ffdde8e6a311d7004d4e7fa5d0ed38123af2c7248b`.
The ECR repository also contained three untagged OCI manifests:
`sha256:4571584eada62151bd518d2200e2527edb64dd3f9e714c54597b0fa19217440a`,
`sha256:0255782e783c64793bc082d327bfed55aaca468ff85dc52de9e73c19f15af609`,
and
`sha256:9e0fc38dcaa34bddbf825f9f26fd216bb091221318a1c4a677e7e93e8af2863f`.
All four exact suffix-`b` digests were deleted before repository teardown.

## Commands executed

- `AWS_PROFILE=ai-platform-pilot-key python3 scripts/terraform_run_monitor.py start apply infrastructure/terraform/module-validation/batch-private-endpoints --run-id batch-private-517-full-apply-20261126b --terraform-arg=/private/tmp/davdeploy-batch-private-endpoints-517-20261126a/full-v3.tfplan` — succeeded; 22 added, one changed, zero destroyed.
- `AWS_PROFILE=ai-platform-pilot-key aws ecr batch-delete-image --region us-east-1 --repository-name davdeploy-batch-private-endpoints-517-20261126a --image-ids <the five exact imageDigest values listed above>` — all five deleted, no failures.
- `AWS_PROFILE=ai-platform-pilot-key python3 scripts/terraform_run_monitor.py start destroy infrastructure/terraform/module-validation/batch-private-endpoints --run-id nova-batch517-cleanup-approved-20261126 --terraform-arg=/private/tmp/davdeploy-batch-private-endpoints-517-20261126a/destroy-approved.tfplan` — Terraform rejected the command before changes because a saved destroy plan must be applied with `terraform apply`.
- `AWS_PROFILE=ai-platform-pilot-key python3 scripts/terraform_run_monitor.py start apply infrastructure/terraform/module-validation/batch-private-endpoints --run-id nova-batch517-cleanup-approved-apply-20261126 --terraform-arg=/private/tmp/davdeploy-batch-private-endpoints-517-20261126a/destroy-approved.tfplan` — succeeded; 0 added, 0 changed, 23 destroyed.
- `AWS_PROFILE=ai-platform-pilot-key aws batch submit-job --region us-east-1 --job-name davdeploy-private-batch-517-20261126a --job-queue davdeploy-batch-private-endpoints-517-20261126a --job-definition davdeploy-batch-private-endpoints-517-20261126a` — submitted job `3d1b3de1-0e7b-4a7f-8605-bb7f37777f2d`. It entered `STARTING` and then failed with status reason `JobQueue deleted`.
- A concurrent monitored cleanup run `nova-batch517-cleanup-approved-apply-20261126` deleted the queue during the job startup. AWS CloudTrail records the exact `DeleteJobQueue` event under the expected account user at `2026-11-26T14:53:02+01:00`; no replacement job was submitted. The image pull and CloudWatch log path therefore remain unproven.
- Independent AWS service-specific `describe` calls checked the exact VPC, subnets, route table, VPC endpoint IDs, security groups/rules, Batch environment and queue, ECR repository, log group, task role, service-linked role, and inactive job definition.
- Suffix-`b` targeted ECR apply `nova-batch517-ecr-apply-20261126b` succeeded; the repository was tagged immutable. A later `docker push ...:20261126b` was rejected because that tag already existed; ECR confirmed the existing digest `sha256:fa6dd10e24e4401dca9523ffdde8e6a311d7004d4e7fa5d0ed38123af2c7248b`, and no overwrite occurred.
- Suffix-`b` full apply `batch-private-517-cycle-b-full-apply-20261126` succeeded at `2026-11-26T16:34:20Z`: 22 added, zero changed, zero destroyed. It created VPC `vpc-03062d08c6e5072e5`, private subnets `subnet-0c07d141bbb9c3bc9` and `subnet-0dc9fa3a6d12b07ac`, interface endpoints `vpce-03a2d7d3bcca8470c` (ECR API), `vpce-0d891c1f0787bf070` (ECR Docker), and `vpce-0ab35bb76c19318c4` (Logs), plus S3 endpoint `vpce-01a8804ed3719c6ab` and the scoped Batch/IAM/logging resources.
- Before submission, AWS reported the compute environment and queue `ENABLED`/`VALID`. Job `62db6ef3-0b17-4d40-8116-078b2dc186ab` used `654654474502.dkr.ecr.us-east-1.amazonaws.com/davdeploy-batch-private-endpoints-517-20261126b@sha256:fa6dd10e24e4401dca9523ffdde8e6a311d7004d4e7fa5d0ed38123af2c7248b`, ran from `2026-11-26T16:39:42Z` to `16:40:09Z`, and completed `SUCCEEDED`, exit code `0`. AWS reports `assignPublicIp=DISABLED` and only private IP `10.241.5.193`.
- The CloudWatch stream `davdeploy/default/4100583bfd2246b8b32763198c068d96` in `/davdeploy/batch-private-endpoints-517-20261126b/batch` returned `DAVDEPLOY_PRIVATE_BATCH_ENDPOINTS_517_OK`. Direct EC2 checks found no internet or NAT gateway in the test VPC; its routes were VPC-local plus the S3 gateway endpoint.
- All four suffix-`b` ECR digests were deleted. Fresh destroy plan contained exactly 23 deletes, zero adds, and zero changes. Monitored saved-plan apply `batch-private-517-cycle-b-destroy-20261126` succeeded at `2026-11-26T16:45:23Z` (supervisor PID `26205`, Terraform PID `26206`, exit code `0`); Terraform reported 0 added, 0 changed, 23 destroyed. Independent service-specific AWS checks confirmed the live stack absent.

## Apply and cleanup evidence

- The first full-plan apply, `batch-private-517-full-apply-20261126a`, failed before creating stack resources because `AWS_PROFILE` was not inherited.
- A subsequent full apply, `batch-private-517-full-apply-20261126b`, succeeded through `scripts/terraform_run_monitor.py` in account `654654474502`, region `us-east-1`, at `2026-11-26T14:40:59Z`. The monitor log is `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/batch-private-517-full-apply-20261126b.log`. Terraform reported 22 added, one changed, and zero destroyed.
- The ECR deletion request named exactly the five digests above and returned five deleted image IDs with no failures.
- Reviewed destroy plan: `/private/tmp/davdeploy-batch-private-endpoints-517-20261126a/destroy-approved.tfplan`. It contained exactly 23 deletes, zero adds, and zero changes. The 23 addresses were the test VPC/network/endpoints/security groups, Batch compute environment/queue/job definition, ECR repository, task role and attachment, CloudWatch log group, and the test-created `AWSServiceRoleForBatch` service-linked role.
- The first monitored invocation used `terraform destroy <saved-plan>` and Terraform rejected it before making changes. The same saved destroy plan was then correctly executed with monitored `terraform apply <saved-plan>`: run ID `nova-batch517-cleanup-approved-apply-20261126`, supervisor PID `11815`, Terraform PID `11816`, exit code `0`. The monitor log is `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-batch517-cleanup-approved-apply-20261126.log`. Terraform reported 0 added, 0 changed, 23 destroyed.
- Independent checks in the same verified AWS account found the ECR repository absent; VPC, subnets, route table, four VPC endpoints, security groups and three security-group rules absent; Batch compute environment and queue absent; CloudWatch log group absent; task execution role and `AWSServiceRoleForBatch` absent. The Terraform state contains no managed resources and the run monitor has no active Terraform operations.
- AWS Batch retains the test job definition as inactive history: `arn:aws:batch:us-east-1:654654474502:job-definition/davdeploy-batch-private-endpoints-517-20261126a:1`. This is not an active workload and was preserved as audit evidence.
- At the time of the independent checks, the Resource Groups Tagging API still returned stale ARN entries for the four deleted VPC endpoints and three deleted security-group rules, despite their service-specific Describe APIs returning not-found/empty results. Its response also listed the retained inactive Batch job definition. Treat those tag-index entries as a reconciliation caveat; the direct service APIs verified the live resources absent.
- Suffix `b` fresh destroy plan `/private/tmp/davdeploy-batch-private-endpoints-517-20261126b/destroy.tfplan` contained 23 deletes, zero adds, and zero changes. Monitored apply `batch-private-517-cycle-b-destroy-20261126` succeeded with 0 added, 0 changed, and 23 destroyed. Independent service-specific checks found the suffix-`b` VPC, subnets, route table, four endpoints, security groups/rules, Batch environment/queue, ECR repository, log group, execution role, and service-linked role absent. Terraform state contains no managed resources and no Terraform operation is active.
- AWS retains suffix-`b` job definition `arn:aws:batch:us-east-1:654654474502:job-definition/davdeploy-batch-private-endpoints-517-20261126b:1` as inactive history. The Resource Groups Tagging API returned stale endpoint/rule/subnet ARNs after teardown, including subnet `subnet-0b4e677b12619be39`; direct EC2 descriptions returned not-found/empty for those IDs. Its response also listed the retained inactive job definition.

## Observed result

Suffix `a`'s job failed because a concurrent cleanup removed its queue during startup. On suffix `b`, Batch reports `SUCCEEDED`, exit code 0, and public-IP assignment disabled; its private subnet had no internet/NAT route, and CloudWatch returned the expected marker. This proves the bounded private ECR and logging path for this exact same-account Batch shape. It does not prove Nova dispatch or cross-account operation.

## Teardown

Both exact test environments were cleaned. Suffix `a`: five ECR digests and 23 managed resources removed. Suffix `b`: four ECR digests and 23 managed resources removed. Both saved destroy plans succeeded through the PID-based monitor; service-specific APIs confirmed live resources absent. AWS retains both job definitions as inactive history. The Resource Groups Tagging API returned stale endpoint/rule/subnet entries as recorded above.

## Local clean-room validation

In an isolated worktree using Compose project `davdeploy-pr517-cleanroom`, ran bootstrap, smoke, API contract, customer-plan E2E, the five canonical demos, seed/restart persistence, trace checks, and `make verify`. Result: 1,971 tests passed with one upstream Starlette/httpx deprecation warning. This used local fixtures only and is not AWS workload evidence. Project containers were removed. The project Postgres volume `davdeploy-pr517-cleanroom_davdeploy-postgres`, local `.venv/`, and `.local/` remain untouched.

## Limits

This proves one successful direct same-account private Batch Fargate job with an immutable ECR digest, private networking, and expected CloudWatch output. It does not prove Nova dispatch, cross-account operation, other Batch image families, general private internet egress, or any other workload family. AWS retains inactive job-definition history; the Resource Groups Tagging API had stale entries as recorded above. The hosted control plane remained untouched.

## Final boundary

The hosted control plane and its state/lock resources were not changed. The evidence is limited to the two disposable same-account AWS Batch cycles above. Suffix `b`'s workload completed successfully, but no Nova dispatch or hosted control-plane lifecycle is claimed.

## Retry cycle b — completed lifecycle evidence

Suffix `b` used test ID `batch-private-endpoints-517-20261126b` and ECR
repository `davdeploy-batch-private-endpoints-517-20261126b` in account
`654654474502`, region `us-east-1`. Its manifest expiry was
`2026-11-26T17:15:00Z`. Preflight verified the account, six available AZs, a
64-vCPU Fargate quota against a one-vCPU ceiling, no pre-existing resources
with this test ID, no Batch environment in `us-east-1`, and no Batch
service-linked role. The targeted ECR apply created one repository; a
digest-pinned full plan then created exactly 22 additional resources.

The single five-minute-bounded job reached `SUCCEEDED`, exit code 0, and
CloudWatch returned the expected echo marker. The task had only private IP
`10.241.5.193` and `assignPublicIp=DISABLED`; direct VPC queries found no
internet gateway or NAT gateway and only local/S3 gateway routes. These
observations prove the private ECR and logging path for this bounded image.

Teardown removed all four exact ECR digests and applied a fresh saved plan
containing exactly 23 deletes. The monitor reports success; independent AWS
service-specific checks confirm the live stack absent. AWS retains the
suffix-`b` job definition as inactive history, and the Resource Groups
Tagging API response still includes stale endpoint/rule/subnet ARNs. No
control-plane resource or retained suffix-`a` audit history was changed.
