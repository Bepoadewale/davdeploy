# ticket517 — Private AWS Batch networking through VPC endpoints

PR: #517
Branch: `feat/private-batch-endpoints-517`

## Problem / goal

The shared Batch module currently hardcodes public-IP assignment on Fargate tasks. Make it configurable without breaking existing callers, then prove a private Batch job can retrieve a private ECR image and send logs through the bounded endpoints added in PR #515.

## Current repo state

- Base backend `main`: `c0b72b1d6b4bdb42158eb720991a01a8990c0024` (PR #516).
- PR #515 source policy bounds ECR API, ECR Docker, and CloudWatch Logs interface endpoints and S3/DynamoDB gateway endpoints. It has no endpoint-traffic lifecycle evidence.
- PR #458 and #252 provide direct Batch lifecycle examples, but neither validates this private endpoint path.
- The hosted control plane must remain untouched. Test resources, if authorized and executed, will be fresh and project-scoped in account `654654474502`, region `us-east-1`.
- Terraform monitor currently has 69 records and zero active runs.

## Research / references used

- AWS [ECR interface endpoints](https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html): private ECR image pulls need `ecr.api`, `ecr.dkr`, and an S3 gateway endpoint; Fargate platform 1.4.0+ needs both ECR endpoints.
- AWS [ECS Fargate networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html): ECR images may be pulled over a private task address when interface endpoints are configured.
- AWS [CloudWatch Logs interface endpoint requirement](https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html): Fargate `awslogs` in a VPC without direct internet access needs a Logs endpoint.
- AWS [PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/): interface endpoints incur hourly per-AZ charges and processed-data fees; partial endpoint-hours are rounded up.
- AWS [VPC pricing](https://aws.amazon.com/vpc/pricing/): NAT gateway hourly/data-processing and public IPv4 charges apply to the current bounded VPC module shape.
- AWS [Fargate pricing](https://aws.amazon.com/fargate/pricing/): task compute is metered by vCPU, memory, and runtime, with per-second billing and a one-minute minimum for Linux/x86.
- AWS [Batch service-linked role documentation](https://docs.aws.amazon.com/batch/latest/userguide/using-service-linked-roles-batch-general.html) and HashiCorp [`aws_batch_compute_environment`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/batch_compute_environment): managed Fargate environments omit the inapplicable custom service-role argument.
- Preflight refreshed 2026-11-26: AWS public rates indicate about $0.01 per interface endpoint ENI-hour and $0.01235 per hour for the 0.25-vCPU/0.5-GB test task; six endpoint ENIs plus the task are about $0.07235 for the first hour before processing/logging. Recheck immediately before apply.
- AWS Fargate On-Demand quota in `us-east-1` is 64 vCPUs; the proposed Batch environment is capped at 1 vCPU. Two selected AZs are available. Before the ECR bootstrap, no resources carried the exact test ID.

## Work planned for the PR

1. Add an `assign_public_ip` input to `modules/batch-compute`, defaulting to current behavior for backwards compatibility.
2. Add a focused Terraform validation root with a fresh two-AZ private-only VPC (no NAT or public IP), ECR API/Docker/Logs endpoints, an S3 gateway endpoint, restricted endpoint SG ingress from the Batch SG, an ECR image, an explicitly owned Batch service-linked role, and one bounded Fargate job with public-IP assignment disabled.
3. Add tests that verify the private/public IP input changes the generated Batch job definition as expected; run Terraform format/validation and required CI.
4. Before AWS apply, verify current us-east-1 Price List prices, Batch/Fargate quotas and availability, review an exact saved plan, and record a maximum of one hour and USD $1.00 estimated total spend. AWS Budgets are not a hard cap.
5. Run one job, prove it reaches `SUCCEEDED`, verify private image retrieval and CloudWatch logs, then use the Terraform run monitor and independently check the exact resources absent after cleanup.
6. The ECR bootstrap repository and images already exist under the exact TestId. The active Nova goal authorizes creation and teardown of disposable AWS validation resources when bounded by an exact manifest and test ID; keep the apply/destroy scope limited to the inventory recorded in `docs/test/test517.md`. If the test is not run, keep evidence explicit about the partial state.

## Acceptance criteria

- [x] Existing module callers retain their current public-IP behavior by default; private networking is an explicit opt-in.
- [x] The test root declares same-plan private subnets without NAT/public IP resources, endpoint bindings, and endpoint SG ingress limited to TCP/443 from the Batch SG; the Batch SG egress is limited to those endpoints and the S3 gateway prefix list.
- [x] The test root sets public-IP assignment to `DISABLED`, requires a SHA256-pinned private ECR image, and constructs a plan-known task-role ARN so the full saved plan exposes the exact job configuration; the private image digest is recorded in `docs/test/test517.md`.
- [x] Focused policy and Terraform-validation tests (641 passed), Terraform formatting/validation, docs conventions, and diff checks pass locally.
- [x] Fargate uses an explicitly managed, untaggable `AWSServiceRoleForBatch`; preflight found it absent and no existing Batch compute environments in 17 enabled regions, defining the exact cleanup boundary.
- [x] Final-head CI for commit `1955e9b5c6c4b4af57c7edd472a5d82776935cd8` passed all seven checks (run `45838409775`).
- [x] Current public pricing, account, quota, AZ availability, exact TestId inventory, and a saved full plan are recorded. The saved plan is scoped to 22 creates and one ECR tag update, with zero deletes. Maximum runtime is one hour and estimated maximum spend is USD $1.00.
- [ ] Within the goal-authorized exact disposable test manifest, a real job succeeds, private ECR image retrieval is observed, and logs arrive through CloudWatch Logs.
- [ ] Exact test resources are destroyed through the run monitor and independently verified absent; AWS-retained inactive job-definition history is listed separately.
- [ ] No hosted control-plane or control-plane state/lock resource is changed; no Nova dispatch claim is made.

## Acceptance status

- [x] Draft PR opened before substantive implementation; matching PR-numbered ticket created.
- [x] Module input, private validation root, and regression test are implemented.
- [x] Focused local validation passes.
- [x] Final-head CI for commit `1955e9b5c6c4b4af57c7edd472a5d82776935cd8` passed all seven checks (run `45838409775`).
- [ ] Cloud experiment pricing, quota, exact plan, and approval prerequisites are satisfied.
- [ ] Customer-side lifecycle and cleanup evidence are recorded within the exact authorized test scope; no Nova dispatch is claimed.
- [ ] PR is reviewed and merged.

## Tests / validation performed

- `pytest tests/test_generated_plan_policy.py tests/test_terraform_validation.py -q`: 641 passed.
- `ruff check tests/test_generated_plan_policy.py tests/test_terraform_validation.py`: passed.
- `terraform fmt -recursive` on the changed roots/modules: passed.
- `make terraform-validate`: passed, including the new private-endpoint test root.
- Focused Terraform tests, full `make terraform-validate`, docs conventions and diff checks passed after the Fargate service-role change. The Batch service-linked role is owned at exact resource address `aws_iam_service_linked_role.batch`; it has no tags.
- Read-only AWS preflight: expected account confirmed, two AZs available, Fargate quota 64 vCPUs, and no pre-existing resources with the test purpose tag.
- Exact targeted ECR plan apply `nova-batch517-ecr-apply-20261126a` succeeded through the Terraform run monitor (supervisor PID `92773`, Terraform PID `92774`); the test image was pushed to the exact new repository and its digest is recorded in `docs/test/test517.md`.
- A second image build/push added a duplicate manifest set to the same test repository; all five exact ECR manifest digests are recorded in `docs/test/test517.md` and require exact cleanup approval.
- Full saved plan `/tmp/davdeploy-batch-private-517-final-reviewed.tfplan` uses the updated Fargate service-linked-role design and contains 22 creates, one ECR expiry-tag update, zero deletes. Its expiry tag is stale, so the plan is inventory evidence only and must not be applied. Recheck current pricing, quota, account inventory, and generate a new plan before any apply. The first monitored full-plan apply failed before creating resources because `AWS_PROFILE` was not passed; state reconciliation found no partial VPC/Batch resources.
- `GITHUB_PR_NUMBER=517 python scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- GitHub CI run `45838409775` passed all seven checks on final head `1955e9b5c6c4b4af57c7edd472a5d82776935cd8`.
- Full isolated local clean-room cycle: bootstrap, smoke, API contract, customer-plan E2E, all five canonical demos, seed/restart persistence, trace check, and `make verify`; 1,971 tests passed with one Starlette/httpx deprecation warning. No AWS resources were used. Project containers were removed; local `.venv/`, `.local/`, and `davdeploy-pr517-cleanroom_davdeploy-postgres` were retained because cleanup of those non-container resources needs explicit approval.
- AWS planning: complete. The ECR bootstrap apply and image push are recorded above. Full Batch/VPC apply awaits explicit AWS cleanup approval for the current exact resource inventory.

## Evidence files produced

`docs/test/test517.md` is reserved for the direct same-account customer-side lifecycle. No workload has been run yet; the file records planned scope only.

## Boundaries

Do not modify hosted control-plane runtime, Terraform state, or lock resources. Before any customer-side apply, verify AWS account `654654474502`, region `us-east-1`, current prices and quotas, and the exact reviewed plan. Do not exceed one hour or the USD $1.00 estimated-cost bound. Keep secrets out of logs. The goal authorization applies to this exact TestId and disposable resource manifest only; do not delete unrelated resources. Preserve AWS-retained inactive Batch definition history and all SageMaker lineage evidence.

## Follow-up work

The private test would validate only this Batch/network/image/logging shape. It does not certify Nova dispatch, all Batch images, general private internet egress, cross-account execution, or any other workload family.
