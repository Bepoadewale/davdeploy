# ticket515 — bind supported VPC endpoints in generated plans

PR: https://github.com/Bepoadewale/davdeploy/pull/515 (draft)
Branch: `feat/vpc-endpoint-policy-515`

## Problem / goal

Allow only the same-region AWS VPC endpoint shapes whose prices were bounded
in merged PR #514: ECR API, ECR Docker, and CloudWatch Logs interface endpoints;
and S3 and DynamoDB gateway endpoints. Bind every endpoint to the existing
supported same-plan VPC topology and reject unknown, cross-region, unsupported,
or weakly bound network configuration. Keep unmodeled network costs as approval
blockers. This is a source-only policy package.

## Current repo state

- Backend `main` is `c6b069037516610bd57cca877dfb52af1dfc71a6` (merged PR #514).
- PR #515 was opened as a draft before implementation.
- `generated_plan_policy.py` currently rejects every `aws_vpc_endpoint` as an
  unsupported route resource. PR #514 now provides bounded endpoint pricing,
  but those endpoint plans remain policy-ineligible until this package.
- No PRs were open when this package started.
- Read-only AWS verification confirmed account `654654474502`, no SageMaker
  endpoint/model/configuration, test role, or artifact bucket, five inactive
  tagged DavDeploy Batch job definitions, no matching Batch queues/compute
  environments, and one retained action-to-context lineage association.
- The Terraform monitor has 67 recorded runs and zero active operations.
- No AWS, Terraform state/lock, hosted control-plane, local protected-file, or
  customer workload changes are in scope.

## Research / references used

- AWS [interface endpoint guide](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html): endpoint ENIs are created in selected subnets; at most one subnet may be selected in each Availability Zone; private DNS requires VPC DNS support/hostnames; endpoint security groups must admit expected traffic; IPv4, IPv6, and dual-stack are distinct modes.
- AWS [gateway endpoint guide](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html): S3 and DynamoDB gateway endpoint routes are associated with selected route tables and have no additional endpoint charge.
- AWS [PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/): interface endpoint hours and processed data are billable; PR #514 provides bounded regional catalog prices for supported services.
- Terraform AWS provider [`aws_vpc_endpoint`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_endpoint) documents endpoint fields and type-specific arguments.

## Work planned for the PR

1. Inspect current plan/configuration representation and related endpoint cost
   assumptions from PR #514.
2. Permit only exact supported service names in the plan region and endpoint
   types `Interface` or `Gateway` as applicable.
3. Require endpoint VPC bindings to the one planned VPC. Interface endpoints
   must use known same-plan private subnets in distinct AZs, private DNS, IPv4,
   and a reviewed security-group boundary for HTTPS from the workload security
   group. Gateway endpoints must bind only reviewed same-plan private route
   tables. Reject unsupported policy documents or endpoint-specific network
   features unless they are explicitly bounded and tested.
4. Preserve all existing route, subnet, NAT, cost, and unknown-value checks.
5. Add positive and adversarial regression cases for each admitted class and
   fail-closed behavior for unsupported services, types, bindings, IP modes,
   DNS modes, subnets, route tables, and security-group sources.
6. Update the Nova goal handoff and capability/evidence matrix truthfully; this
   remains source policy evidence, not deployment or customer-execution proof.

## Acceptance criteria

- [x] Only ECR API, ECR Docker, and CloudWatch Logs same-region interface
  endpoints and S3/DynamoDB gateway endpoints can pass the VPC endpoint rule.
- [x] Each interface endpoint is bound to the same planned VPC and one or more
  known private subnets, no more than one selected subnet per AZ, private DNS,
  IPv4, and a narrowly reviewed HTTPS security-group path. Every security-group rule
in the endpoint plan must also bind to a known same-plan security group.
- [x] Each gateway endpoint is bound to the same planned VPC and supported
  same-plan private route tables; its plan shape has no unsupported endpoint
  arguments or route overrides.
- [x] Unsupported services/types, missing or unknown bindings, cross-region
  services, public/ambiguous subnet selection, broad ingress, unknown security-group rule bindings, and unreviewed
  endpoint/network paths fail closed or remain explicit review blockers.
- [x] Existing VPC route and NAT policy remains unchanged for endpoint-free
  plans; the existing unsupported-route regression remains valid.
- [x] Focused policy and pricing tests pass, documentation conventions pass, and `git diff --check` passes.
- [x] All seven code-head CI checks passed on `870ce27` in run
  [45724497158](https://github.com/Bepoadewale/davdeploy/actions/runs/45724497158).
- [x] All seven documentation-head CI checks passed on `61db1e6` in run
  [45774078900](https://github.com/Bepoadewale/davdeploy/actions/runs/45774078900).
- [ ] Fresh CI and clean-room evidence for the added unknown security-group
  rule-binding regression are pending.
- [ ] The PR is reviewed and merged.
- [x] No AWS resources, Terraform state/locks, hosted control-plane resources,
  customer workloads, `--only-show-errors`, or `.venv-pr399/` are changed.

## Acceptance status

- [x] Draft PR opened before substantive implementation and matching ticket created.
- [x] Implementation and endpoint regression coverage are complete locally.
- [x] Full local verification and documentation validation pass on current
  worktree changes: `make VENV=... verify` reports 1,970 passed; docs checks
  and Ruff pass.
- [x] All seven checks passed in run `45774078900` on source commit `61db1e6`.
- [ ] The subsequent fail-closed rule-target check and regression test require
  a fresh final-head CI run before merge.
- [x] The prior clean-room sequence and cleanup at code head `870ce27` are
  complete. The new rule-binding regression still requires a fresh full clean-room
  cycle before merge.
- [ ] Review and merge remain pending.
- [x] No customer workload or cloud mutation is in scope.

## Tests / validation performed

- Focused policy/pricing tests before the final rule-binding fix: 794 passed.
- Current `tests/test_generated_plan_policy.py`: 638 passed after the
  rule-binding regression was added.
- Ruff check on the changed policy and test files passed.
- `git diff --check` passed.
- Full repository `make VENV=/Users/adewale/Projects/davdeploy/.venv verify` on current worktree changes: 1,970 passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration passed. One upstream Starlette/httpx deprecation warning was emitted.
- `GITHUB_PR_NUMBER=515 /Users/adewale/Projects/davdeploy/.venv/bin/python scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- All seven GitHub final-head checks passed on source commit `61db1e6` in
  [run 45774078900](https://github.com/Bepoadewale/davdeploy/actions/runs/45774078900).
- Isolated local clean-room worktree `/private/tmp/davdeploy-pr515-cleanroom-20261126`
  at `870ce27` passed initial clean from an empty project, bootstrap, smoke,
  simple/complex/degraded/Day-2/failure/readiness demos, trace check, and full
  verification (1,969 passed). A later read-only inventory confirmed the nine
  `davdeploy-pr515-cleanroom` containers, volume
  `davdeploy-pr515-cleanroom_davdeploy-postgres`, network
  `davdeploy-pr515-cleanroom_default`, and generated `.venv` and `.local` are
  absent after the scoped cleanup. Independent checks confirmed this; the
  worktree remains.
- The final code review identified the need to reject unknown security-group
  rule targets whenever an interface endpoint is present. The new regression
  test and fail-closed check pass locally. No GitHub review has been submitted.


## Evidence files produced

No `docs/test/test515.md` is expected because this package is source-only and
must not execute a customer workload.

## Boundaries

Do not execute Terraform or change AWS, hosted control-plane, state, or lock
resources. Do not delete existing audit/lineage evidence or inactive job
definitions. Do not claim Nova-dispatched or customer execution. Preserve the
protected untracked file and `.venv-pr399/` in the original checkout.

## Follow-up work

Unpriced egress, cross-AZ paths, unsupported endpoint services and types,
network ACL association/precedence, VPN, peering, transit gateways, and
effective service reachability remain separate approval blockers until
independently bounded and evidenced.
