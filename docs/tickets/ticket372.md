# ticket372 — add bounded RDS subnet-group metadata reads

PR: [#372](https://github.com/Bepoadewale/davdeploy/pull/372) (draft)  
Branch: `feat/nova-rds-subnet-group-plan-access-372`

## Problem / goal

After PR #371, the fixed Nova planner profile supports RDS DB instances,
Aurora clusters and cluster instances, but rejects `aws_db_subnet_group` even
though the Aurora implementation contract includes it. Add only the metadata
read permission and exact resource ARN needed to track declared subnet groups.
Do not add VPC-wide or EC2 discovery in this PR.

## Current repo state

- Backend `main` is `fb60bf3bf10ce52a4ad7037f387ab1f4d9f764d3` after PR #371.
- PR #371's bounded RDS profile allows `DescribeDBInstances`,
  `DescribeDBClusters`, and `ListTagsForResource`; exact DB and cluster ARNs
  are derived from validated identifiers and trusted account/region inputs.
- `aws_db_subnet_group` remains unsupported and will fail closed before the
  customer plan credentials are assumed.
- Hosted Nova planning/apply gates remain disabled. No customer plan role is
  installed or verified; PR #318 remains held.

## Research / references used

- [AWS RDS service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_rds.html): `DescribeDBSubnetGroups` supports the `subgrp` resource type, and `ListTagsForResource` supports RDS subnet groups.
- [AWS RDS `DescribeDBSubnetGroups` API](https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_DescribeDBSubnetGroups.html): a named request can return only the selected group.
- [HashiCorp AWS provider `aws_db_subnet_group` resource documentation](https://github.com/hashicorp/terraform-provider-aws/blob/v6.69.1/website/docs/r/db_subnet_group.html.markdown)
- Existing plan-access profile: `apps/api/src/davdeploy/nova_plan_access.py`.

## Work planned for the PR

- Add `aws_db_subnet_group` to the supported plan resource list.
- Derive only `arn:<trusted-partition>:rds:<trusted-region>:<trusted-account>:subgrp:<name>` from a concrete valid `name` or an allowed declared typed name reference.
- Add `rds:DescribeDBSubnetGroups` to the plan role and customer template; retain the existing exact RDS tag-read action and explicit deny boundary.
- Add positive exact-ARN and negative malformed/unknown/wildcard/reference/action tests.
- Reconcile the status matrix for PR #371 as merged source but not deployed, preserving the missing live role and hosted plan evidence.

## Acceptance criteria

- [x] Subnet groups receive exact account/region/subgrp ARN-scoped metadata reads.
- [x] Missing, malformed, unknown, wildcard, or unsafe references fail before role assumption.
- [x] Only `DescribeDBSubnetGroups` and scoped `ListTagsForResource` are added; RDS writes, data reads and secret contents remain denied.
- [x] The customer role template and session-policy action list match.
- [x] Existing DB/cluster/S3/SQS/DynamoDB/API/IAM profiles retain their tested behavior.
- [x] PR #371 status is reconciled as source merged but not deployed; no customer role or hosted plan is claimed.
- [ ] Focused tests, full `make verify`, clean-room proof, docs checks, current-head review and required final-head CI pass.
- [x] No feature flag, customer role, plan, approval, apply or customer workload is enabled or executed by this PR.

## Acceptance status

- [x] Implementation and local security review complete; exact RDS action, ARN, canonical subnet-group name, and typed-reference checks were reviewed with no blocker found.
- [x] Focused tests (37) and full `make verify` (1,038 tests) pass.
- [ ] Clean-room and required final-head CI pass.
- [x] No runtime/customer-resource mutation occurred.

## Tests / validation performed

Focused tests (37), `make verify` (1,038), Ruff, documentation conventions,
and diff checks pass locally. Clean-room proof and final-head CI remain
outstanding. See `docs/test/test372.md` and update it as those gates complete.

## Evidence files produced

- `docs/test/test372.md`

## Boundaries

This adds only RDS subnet-group metadata access. It does not grant EC2/VPC
discovery, add subnet or security-group resources to the plan role, enable
hosted planning, supply regional pricing, install a customer role, or certify
application deployment, health, recovery or teardown. Tenant-specific remote
state, exact cost-bound approval and the end-to-end hosted customer flow remain
separately incomplete. Pricing PR #318 remains held.

## Follow-up work

After PR #372, assess the remaining network-read requirements separately;
do not widen the customer role to broad EC2 read access without a concrete
resource-scoped policy design and acceptance tests.
