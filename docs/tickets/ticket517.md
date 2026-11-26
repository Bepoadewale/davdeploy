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
- Terraform monitor last reconciled at 67 records and zero active runs.

## Research / references used

- AWS [ECR interface endpoints](https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html): private ECR image pulls need `ecr.api`, `ecr.dkr`, and an S3 gateway endpoint; Fargate platform 1.4.0+ needs both ECR endpoints.
- AWS [ECS Fargate networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html): ECR images may be pulled over a private task address when interface endpoints are configured.
- AWS [CloudWatch Logs interface endpoint requirement](https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html): Fargate `awslogs` in a VPC without direct internet access needs a Logs endpoint.
- AWS [PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/): interface endpoints incur hourly per-AZ charges and processed-data fees; partial endpoint-hours are rounded up.
- AWS [VPC pricing](https://aws.amazon.com/vpc/pricing/): NAT gateway hourly/data-processing and public IPv4 charges apply to the current bounded VPC module shape.
- AWS [Fargate pricing](https://aws.amazon.com/fargate/pricing/): task compute is metered by vCPU, memory, and runtime, with per-second billing and a one-minute minimum for Linux/x86.

## Work planned for the PR

1. Add an `assign_public_ip` input to `modules/batch-compute`, defaulting to current behavior for backwards compatibility.
2. Add a focused Terraform validation root with a fresh two-AZ VPC, private subnets, one NAT, ECR API/Docker/Logs endpoints, an S3 gateway endpoint, restricted endpoint SG ingress from the Batch SG, an ECR image, and one bounded Fargate job with public-IP assignment disabled.
3. Add tests that verify the private/public IP input changes the generated Batch job definition as expected; run Terraform format/validation and required CI.
4. Before AWS apply, verify current us-east-1 Price List prices, Batch/Fargate quotas and availability, review an exact saved plan, and record a maximum of one hour and USD $1.00 estimated total spend. AWS Budgets are not a hard cap.
5. Run one job, prove it reaches `SUCCEEDED`, verify private image retrieval and CloudWatch logs, then use the Terraform run monitor and independently check the exact resources absent after cleanup.
6. No AWS apply or deletion occurs from this PR until exact resource cleanup approval is recorded. If the test is not run, keep test evidence explicitly marked not executed.

## Acceptance criteria

- [x] Existing module callers retain their current public-IP behavior by default; private networking is an explicit opt-in.
- [x] The test root declares same-plan private subnets, endpoint bindings, and endpoint SG ingress limited to TCP/443 from the Batch SG; the Batch SG egress is limited to those endpoints and the S3 gateway prefix list.
- [x] The test root sets public-IP assignment to `DISABLED` and requires a SHA256-pinned private ECR image; an authenticated plan and image digest are not yet recorded.
- [x] Focused policy tests (639 passed), Terraform formatting/validation, docs conventions, and diff checks pass locally.
- [ ] Final-head CI passes.
- [ ] Before AWS apply, current pricing/quota/capacity and exact resource inventory are recorded; maximum runtime is one hour and estimated maximum spend is USD $1.00.
- [ ] With explicit cleanup authorization, a real job succeeds, private ECR image retrieval is observed, and logs arrive through CloudWatch Logs.
- [ ] Exact test resources are destroyed through the run monitor and independently verified absent; AWS-retained inactive job-definition history is listed separately.
- [ ] No hosted control-plane or control-plane state/lock resource is changed; no Nova dispatch claim is made.

## Acceptance status

- [x] Draft PR opened before substantive implementation; matching PR-numbered ticket created.
- [x] Module input, private validation root, and regression test are implemented.
- [x] Focused local validation passes.
- [ ] Final-head CI passes.
- [ ] Cloud experiment pricing, quota, exact plan, and approval prerequisites are satisfied.
- [ ] Customer-side lifecycle and cleanup evidence are recorded; no Nova dispatch is claimed.
- [ ] PR is reviewed and merged.

## Tests / validation performed

- `pytest tests/test_generated_plan_policy.py -q`: 639 passed.
- `ruff check tests/test_generated_plan_policy.py`: passed.
- `terraform fmt -recursive` on the changed roots/modules: passed.
- `make terraform-validate`: passed, including the new private-endpoint test root.
- `GITHUB_PR_NUMBER=517 python scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- GitHub CI: pending on final head.
- AWS planning/apply: not started.

## Evidence files produced

`docs/test/test517.md` is reserved for the direct same-account customer-side lifecycle. No workload has been run yet; the file records planned scope only.

## Boundaries

Do not modify hosted control-plane runtime, Terraform state, or lock resources. Before any customer-side apply, verify AWS account `654654474502`, region `us-east-1`, current prices and quotas, and the exact reviewed plan. Do not exceed one hour or the USD $1.00 estimated-cost bound. Keep secrets out of logs. No AWS resource may be destroyed without explicit approval in this conversation. Preserve inactive Batch definition records and all SageMaker lineage evidence.

## Follow-up work

The private test would validate only this Batch/network/image/logging shape. It does not certify Nova dispatch, all Batch images, general private internet egress, cross-account execution, or any other workload family.
