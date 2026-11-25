# ticket514 — price bounded interface VPC endpoints

PR: https://github.com/Bepoadewale/davdeploy/pull/514 (draft)
Branch: `feat/interface-vpc-endpoint-pricing-514`

## Problem / goal

The bounded AWS Batch estimate now prices Fargate compute, explicitly
configured CloudWatch Logs, a same-plan private ECR image repository, and
explicit public IPv4 assignment. Its network path remains a blocker. Add
catalog-backed pricing for one narrowly defined `aws_vpc_endpoint` interface
endpoint shape, with exact plan binding and trusted usage bounds for endpoint
availability and processed data. Keep unsupported endpoint types and all other
unmodeled network costs approval-blocking. This is source-only.

## Current repo state

- Backend `main` is `e9f4cdb660da4b4971615b5713b5d64846bd279` (PR #513); no PRs
  were open at package start.
- PR #500 bounds one public/private VPC topology; PR #502 prices its NAT path.
- PRs #507 and #509–#512 price selected Batch compute, log, image-storage, and
  public-address costs while retaining the general supporting-cost blocker.
- The current AWS Price List abstraction requires exactly one regional product
  match and preserves SKU, digest, and effective/published timestamps.
- No AWS workload, Terraform state, hosted control plane, or customer execution
  is in scope. Preserve the protected untracked file and `.venv-pr399/` in the
  original checkout.

## Research / references

- AWS [interface endpoint guide](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html): interface endpoints are billed for hourly usage and data processing; one subnet can be selected per Availability Zone and each selected subnet receives an endpoint network interface.
- AWS [VPC billing codes](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-billing-usage-reports.html): `VpcEndpoint-Hours` measures provisioned interface endpoint time; `VpcEndpoint-Bytes` measures processed interface endpoint data.
- AWS [gateway endpoint guide](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html): S3 and DynamoDB gateway endpoints have no additional charge.
- AWS [EKS networking cost guidance](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-networking.html): interface endpoint hourly and processing charges apply; gateway endpoints have no hourly or data-transfer endpoint charge; AWS states inter-AZ endpoint transfer is not charged in this context.
- Use the regional AWS Price List for rates. Do not hardcode prices or infer a free service/network path from endpoint type alone.

## Work planned

1. Add strict, versioned trusted usage assumptions keyed by exact planned interface-endpoint Terraform address. Bind monthly provisioned hours and processed-GB ranges; require exact key/resource matching and bounded values.
2. Recognize only an explicitly known interface endpoint configuration with a supported, same-plan VPC/subnet association. Derive the selected Availability Zone count from plan-bound subnet facts/references, enforce one selected subnet per AZ, and fail closed when IDs or AZs are unknown or ambiguous.
3. Add regional Price List matchers for endpoint hours and processed bytes, using exact product dimensions and retaining catalog metadata. If product matches are tiered or ambiguous, implement tier accounting only with exact documented dimensions; otherwise leave that price unsupported and fail closed.
4. Price endpoint hours per selected AZ and processed data according to trusted monthly bounds. Do not emit an endpoint line for S3/DynamoDB gateway endpoints; explicitly reject unsupported Gateway Load Balancer, service-network, cross-region, shared-subnet, or other endpoint variants unless separately modeled.
5. Keep plan-level pricing incomplete and approval-ineligible for unknown endpoint traffic, unsupported endpoints, missing prices/usages, NAT/egress/transfer paths, or any other material supporting cost. Do not enable Batch approval.
6. Add regression tests for eligible interface endpoints, exact subnet/AZ binding, usage mismatches, unknown/ambiguous plan values, no-price/no-match behavior, unsupported endpoint types, gateway endpoints, stale assumptions, evidence round trips, and persistent approval blocking.
7. Update the Nova capability/evidence matrix, composed execution handoff, and this ticket with truthful boundaries and validation evidence.

## Acceptance criteria

- [ ] A bounded interface endpoint emits regional endpoint-hour and data-processing cost lines tied to its exact planned address, trusted usage bounds, selected AZ count, and saved-plan digest.
- [ ] The endpoint shape and AZ count are derived from known exact plan facts; unknown, stale, ambiguous, or mismatched facts fail closed.
- [ ] Only exact catalog rates and metadata are used; no customer-supplied prices or guessed rate/product selection.
- [ ] S3/DynamoDB gateway endpoints receive no endpoint charge only when their exact supported type is established; other endpoint types fail closed.
- [ ] Any unpriced endpoint/network dependency continues to block pricing completeness and approval; the PR does not enable Batch approval or execution.
- [ ] Focused tests, full required local verification, documentation conventions, and diff whitespace checks pass.
- [ ] All required final-head CI checks pass before merge.
- [ ] No AWS resources, Terraform state/locks, hosted control-plane resources, protected local files, or customer workloads are changed.

## Acceptance status

- [ ] Implementation complete.
- [ ] Local validation complete.
- [ ] Final-head CI passed.
- [ ] PR reviewed and merged.
- [ ] Merged-main CI passed.
- [x] No customer workload or cloud mutation is in scope.

## Evidence files

No `docs/test/test514.md` is expected unless this PR performs a customer
workload run. The planned implementation is source-only.

## Boundaries and follow-up

Do not execute Terraform, mutate AWS, access/change the hosted control plane,
enable Nova execution or approval, delete resources, or claim a Nova/customer
workload. If service-specific endpoint dimensions cannot be safely selected
from AWS Price List, keep those resources approval-blocking and document the
unsupported shape. Follow-up coverage may separately address gateway
endpoints, Gateway Load Balancer endpoints, cross-region PrivateLink, and
network data-transfer paths.
