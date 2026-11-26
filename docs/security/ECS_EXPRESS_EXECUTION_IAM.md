# ECS Express execution identity and permission boundary

Status: design and source review only. The ECS Express renderer remains
disabled. No AWS role or workload was created or changed for this review.

## Current runner path

The current ECS Express worker receives
`DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN`, reads the connection ExternalId from
the platform secret store, and assumes that role for a 3,600-second session.
The STS request has no inline `Policy` or managed `PolicyArns` session policy.
That session is then used for planning, saved-plan apply and destroy,
observation, and cleanup checks.

The customer connection template's `administrator-pilot` mode creates
`davdeployExecution-${ConnectionId}` with AWS `AdministratorAccess`. The
connection verification path proves that role assumption succeeds and returns
the expected account; it does not inspect the role's full permission profile.
Therefore, when this role is configured, the current ECS Express runner gets
account-wide administrator permissions. The renderer is disabled, and this
review did not assume that role or make any AWS request.

PR #525 provisions the separate ECS task execution and ECS infrastructure
roles. It verifies their trust relationships, tags, and attached managed
policies. Those service roles are passed to ECS; they do not narrow the
permissions of the DavDeploy caller that creates or deletes the Express
service.

## Permission responsibilities required before execution

| Identity | Required scope | Must not do |
| --- | --- | --- |
| Discovery role | Read-only account inventory and pricing for an explicitly selected account and region | Plan, mutate, or execute a workload |
| Plan role | Read APIs needed to plan the supported root and verify the connection role profile | Create, update, or delete workload resources |
| State role | One customer state bucket prefix, one lock table, and the configured state encryption key | Act as the Terraform AWS provider or access unrelated state |
| Apply/destroy role | A fixed maximum action ceiling for supported resources, narrowed for each run by deterministic policy derived from the exact saved plan | Use `AdministratorAccess`, accept an LLM-supplied policy, or act outside the approved plan |
| Observation role | Read only the resources and health endpoints needed to verify readiness, change, recovery, and absence | Change workload or account configuration |
| Image publisher role | Push the one approved image digest to the connection/project ECR repository | Provision workload infrastructure or read unrelated repositories |
| ECS task execution role | ECS task image pull and logging permissions for the selected task | Manage customer infrastructure |
| ECS infrastructure role | AWS-documented managed permissions used by ECS Express to create and manage its supporting service resources | Be assumed directly by DavDeploy |

The state and provider sessions must remain distinct. The S3 backend and lock
table need their own narrowly scoped credentials; Terraform's AWS provider
must use the phase-specific plan or apply role. Do not let the S3 backend
profile become the provider's general customer credential.

## Exact-plan apply policy contract

1. Retrieve and verify the exact saved plan that was reviewed and approved.
   Reject a stale plan, mismatched plan digest, wrong account, wrong region,
   different project, or missing approval before requesting apply credentials.
2. Convert the saved plan into JSON using a pinned Terraform binary. A
   deterministic allowlist maps every managed resource type and action in the
   supported ECS Express root to the minimal AWS API actions and resource
   constraints. Ignore no unknown resource change: reject it.
3. Scope existing resources to their exact ARNs. For newly created resources
   whose IDs do not exist at plan time, require documented service-supported
   request-tag or other condition keys. If an action cannot be bounded from
   trusted plan data, keep the plan ineligible for apply.
4. Add `iam:PassRole` only for the connection-scoped task execution and
   infrastructure role ARNs from PR #525. Require the AWS-documented
   `iam:PassedToService` values for ECS and ECS tasks. No role creation,
   policy attachment, or arbitrary pass-role permission belongs in this
   workload runner.
5. Compute a canonical digest of the generated permission policy and bind it
   to the saved-plan digest, account, region, project, authorization, and run
   record. The policy must come from deterministic backend code and trusted
   persisted data; callers and Nova cannot submit or edit it.
6. Verify the customer role's trust, path, tags, permissions boundary, exact
   inline and managed policies, and required pass-role conditions before
   issuing short-lived credentials. Simulate the expected action/resource
   pairs where supported. Simulation is evidence, not complete proof of
   organization policies or resource-based permissions.
7. Fail closed when the policy exceeds the STS limit, the role has drifted,
   simulation returns an unexpected decision, the plan includes an
   unsupported type/action, or required resource identities are unknown.
8. Plan, apply, observe, and destroy use different phase-specific credentials.
   Destroy requires a separately generated and approved destroy plan; it must
   not reuse the create-plan policy or imply approval from the earlier apply.

The existing `nova_apply_access.py` policy builder currently supports S3,
SQS, and DynamoDB profiles only. It is not an ECS permission policy. Before
adding ECS Express support, implementation must map and test every resource in
the pilot root: VPC, internet gateway, subnets, route tables and associations,
ECR repository, CloudWatch log group, Express service, and the two passed ECS
service roles. Service actions that require wildcard resources need a
reviewed, narrow condition contract rather than an unrestricted wildcard.

AWS session policies reduce identity-based permissions by intersection and
cannot grant more permission than the assumed role. Do not rely only on an
implicit session-policy deny: a same-account resource policy can grant access
directly to an assumed-role session. The implementation must account for
resource-based policies and preserve explicit-deny and permission-boundary
controls where applicable.

## Validation and release gates

The follow-up implementation must include deterministic unit tests for
create/update/delete plans, replacements, exact resource scope, `iam:PassRole`
conditions, unknown IDs, unsupported resources, policy-size limits, policy
digest binding, and explicit denial outside the plan. It must verify role
profiles and test that the runner chooses the intended role for each phase.
No successful local policy simulation is evidence that the role is safe in
every customer account.

Before any cloud run, an explicit bounded test authorization must name the
account, region, resource limits, maximum runtime, estimated cost, exact plan,
and cleanup procedure. Use customer-side isolated state; do not touch the
hosted control plane, its state, or locks. After authorization, validate
assumption identities, action outcomes, plan-bound policy evidence, application
health, update/recovery behavior, and independent resource absence. Keep the
renderer disabled until those checks and final review pass.

## Sources

- [STS AssumeRole session policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-api.html)
- [IAM policy evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html)
- [ECS service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html)
- [ECS Gateway permission troubleshooting](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/gateway-troubleshooting.html)
- [`nova_apply_access.py`](../../apps/api/src/davdeploy/nova_apply_access.py)
- [`customer-nova-apply-role.yaml`](../../infrastructure/cloudformation/customer-nova-apply-role.yaml)
- [`customer-discovery-role.yaml`](../../infrastructure/cloudformation/customer-discovery-role.yaml)
- [`customer-workload-ecs-express-pilot.sh`](../../scripts/customer-workload-ecs-express-pilot.sh)
