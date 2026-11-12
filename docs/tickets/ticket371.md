# ticket371 — add bounded RDS metadata reads to Nova plan access

PR: #371  
Branch: `feat/nova-rds-plan-access-371`

## Problem / goal

The fixed Nova plan-access profile rejects `aws_db_instance`,
`aws_rds_cluster`, and `aws_rds_cluster_instance`, even though actual-plan
policy and the generated secret-reference contract already support RDS
resources. Add only the read permissions and exact resource scoping needed to
plan declared RDS instances and clusters. Preserve explicit deny of mutation
and data-content operations.

## Current repo state

- Backend main is `6813a4bf62d66ad9d7f3778481ae78cca69ad511` after docs PR #370.
- `hashicorp/aws` provider is pinned at `6.69.1` in the serverless control-plane
  Terraform lockfile.
- `apps/api/src/davdeploy/nova_plan_access.py` accepts S3, SQS, DynamoDB,
  Lambda, API Gateway and selected IAM resources; it rejects RDS types.
- The customer plan-role CloudFormation profile also has no RDS read actions.
- Plan-role trust/account verification is enabled, but no customer plan role
  exists in the pilot account. The plan runner, broker, state API, reviews and
  hosted certification remain disabled; no customer plan has run.
- Pricing PR #318 remains held. This PR will not enable execution or approval.

## Research / references used

- [Amazon RDS IAM service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_rds.html): `DescribeDBInstances` and `DescribeDBClusters` support DB/cluster resource types; `ListTagsForResource` is an RDS read action.
- [How Amazon RDS works with IAM](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/security_iam_service-with-iam.html)
- [HashiCorp AWS provider `aws_db_instance`](https://github.com/hashicorp/terraform-provider-aws/blob/v6.69.1/website/docs/r/db_instance.html.markdown)
- [HashiCorp AWS provider `aws_rds_cluster`](https://github.com/hashicorp/terraform-provider-aws/blob/v6.69.1/website/docs/r/rds_cluster.html.markdown)
- [PR #367 bounded RDS managed-secret reference contract](docs/tickets/ticket367.md)

## Work planned for the PR

- Add `aws_db_instance`, `aws_rds_cluster`, and `aws_rds_cluster_instance` to
  the plan profile only when a concrete, known database identifier can be
  bound to an exact ARN in the trusted account and region.
- Add exact RDS metadata-read actions to the fixed planner session profile and
  customer role template; keep the explicit deny list aligned.
- Reject missing, unknown, expression-based, wildcard, malformed, or
  cross-account RDS identifiers before role assumption.
- Add tests for exact instance/cluster ARN scoping, deterministic policy
  digests, action denial, unsupported resource types, and template boundaries.
- Keep the worker and all hosted execution gates unchanged and disabled.

## Acceptance criteria

- [x] RDS DB instances, Aurora clusters, and cluster instances receive only exact account/region/resource-scoped
  read actions in the generated session policy.
- [x] Missing or non-concrete identifiers fail before customer credentials are
  assumed.
- [x] No RDS write, snapshot restore/export, log-content, secret-content, or
  database-data action is granted.
- [x] The customer role template's RDS read profile and explicit `NotAction`
  deny remain consistent with the session policy.
- [x] Existing S3/SQS/DynamoDB/API/IAM profiles retain their exact behavior.
- [ ] Focused tests, `make verify`, clean-room proof, docs checks, and required
  GitHub CI pass.
- [ ] No feature flag, AWS role, customer plan, approval, apply, or workload is
  enabled or executed by this PR.

## Acceptance status

- [ ] Implementation and security review complete.
- [ ] Focused and full verification pass.
- [ ] Required CI and clean-room gates pass on the final PR head.
- [ ] No runtime or customer-resource mutation occurs.

## Tests / validation performed

Focused tests (27) and `make verify` (1,028 tests), Ruff, docs conventions, and
diff checks pass locally. Clean-room proof, final-head CI and review remain
outstanding. See `docs/test/test371.md` and update it as those gates complete.

## Evidence files produced

- `docs/test/test371.md`
- `apps/api/src/davdeploy/nova_plan_access.py`
- `infrastructure/cloudformation/customer-discovery-role.yaml`
- `tests/test_nova_plan_access.py`
- `tests/test_customer_aws_connection_contract.py`

## Boundaries

This PR changes the plan role's read-only metadata capability only. It does not
enable hosted planning or apply, install a customer role, grant data or secret
reads, add RDS resource renderers, or make plans approvable. Pricing PR #318
remains held.

## Follow-up work

Verify the installed customer role and exact Terraform plan under a real
authenticated workspace-admin connection, then continue tenant-scoped remote
state and complete pricing before considering hosted planning approval.
