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

## AWS authorization map review (2026-11-27)

This map is sourced from the current AWS Service Authorization Reference and
ECS API reference. It is a review artifact, not an executable policy. AWS
provider behavior and dependent actions must still be verified against the
pinned Terraform AWS provider version before any role is authorized.

| Pilot-root resource or call | Required authorization surface | Scoping evidence and remaining concern |
| --- | --- | --- |
| VPC, internet gateway, subnet, route table | EC2 create/modify/delete actions, plus tag actions | EC2 exposes resource ARNs and request/resource tag conditions for these resources. New subnet creation also authorizes against its parent VPC. The saved plan does not know newly created IDs; a policy needs an explicit request-tag contract and must bind relationship actions to tagged VPC/subnet/route-table resources. |
| Route-table association | `ec2:AssociateRouteTable`, `ec2:DisassociateRouteTable` | The initial plan does not know newly created subnet and route-table IDs. EC2 authorization must therefore constrain the association to both resources through supported resource-tag conditions, with exact `ConnectionId`, `ProjectId`, and plan-digest tags. Verify the provider's tag-on-create and authorization context for the association API; reject the plan if both sides cannot be constrained. The later ECS service plan can use the now-known subnet IDs. |
| ECR repository | ECR repository resource actions and tag operations | Repository name in this root is deterministic; use its exact same-account, same-region repository ARN. `ecr:GetAuthorizationToken` is separate and resource `*`; it belongs only to the image-publisher identity, not Terraform apply. |
| CloudWatch log group | Log-group resource actions and tag operations | The log-group name is deterministic; use its exact ARN including the `:*` form only where the action requires log streams. Keep log reads in observation credentials. |
| ECS Express service create/update | `ecs:CreateExpressGatewayService` or `ecs:UpdateExpressGatewayService`, plus `ecs:AssociateGatewayWithCluster`, `ecs:CreateCluster`, `ecs:CreateGateway`, `ecs:RegisterTaskDefinition`, `ecs:TagResource`, and exact `iam:PassRole` as listed by AWS | AWS documents service/resource tags, `ecs:cluster`, `ecs:subnet`, CPU/memory and task-definition condition keys. The current runner already has a staged path: a foundation plan/apply with `enable_service=false`, then image publication, then a separate service plan/apply with `enable_service=true`. The service plan can use subnet IDs from the already-applied foundation state. The IAM design must prove these are distinct, exact plan digests and must scope the service plan to verified subnet and service-role ARNs. The ECS API internally creates or associates several resources that do not appear as separate Terraform resource changes; their resource ARNs and condition behavior still need explicit policy tests. |
| ECS Express service deletion | `ecs:DeleteExpressGatewayService` on the exact service ARN | AWS says this action stops tasks and removes its associated load balancer, target groups, security groups, scaling policies and managed components. It requires a separately approved destroy plan; no broad ELB or Auto Scaling caller access should be inferred from the deletion side effect. |
| Terraform data-source and account/region checks | Read-only EC2 availability-zone, IAM role and STS identity actions | These reads are not necessarily represented as managed resource changes. The plan-role profile must cover them separately; they must not be added to apply permissions without exact resource/action justification. |

AWS documents that `CreateExpressGatewayService` provisions Application Load
Balancers, target groups, security groups and auto scaling components, and that
an ECS infrastructure role is supplied for AWS to manage those components.
That AWS-managed role is distinct from the DavDeploy caller role. The caller
must receive only ECS API permissions and exact `iam:PassRole`, not the
infrastructure role's ELB/EC2/Auto Scaling policy.

The AWS ECS authorization table lists the composite create/update dependent
actions and supports tag, cluster and subnet conditions. A single saved plan
that creates the VPC/subnets and ECS service cannot bind `ecs:subnet` to IDs
that do not yet exist. The existing runner avoids that by applying the
foundation stage first and planning service creation afterward. This sequencing
must be bound to separately approved plan digests and phase credentials. Tests
must verify the provider's exact API calls, names, resource ARNs, condition
context, and `iam:PassedToService` values for the two connection-scoped roles.

No ECS policy builder or role was changed by this review. The renderer remains
disabled until the action map is complete, tested against the pinned provider,
and combined with separate plan, state, apply/destroy, observation and image
publishing identities. See the official references below.

## Additional official references

- [Amazon EC2 actions, resources, and condition keys](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html)
- [Amazon ECR actions, resources, and condition keys](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecr.html)
- [CloudWatch Logs actions, resources, and condition keys](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html)
- [Amazon ECS actions, resources, and condition keys](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html)
- [CreateExpressGatewayService API](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_CreateExpressGatewayService.html)
- [DeleteExpressGatewayService API](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_DeleteExpressGatewayService.html)
- [IAM actions, resources, and condition keys](https://docs.aws.amazon.com/service-authorization/latest/reference/list_iam.html)

## Pinned Terraform provider operation map (2026-11-27)

The pilot lockfile pins `hashicorp/aws` 6.73.0. I reviewed the resource
implementation at the corresponding upstream tag
[`v6.73.0/internal/service/ecs/express_gateway_service.go`](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/ecs/express_gateway_service.go).
The file confirms these direct ECS API calls:

| Terraform lifecycle path | Provider calls in v6.73.0 | IAM follow-up |
| --- | --- | --- |
| Create | Existence check through the shared `DescribeServices` helper; `CreateExpressGatewayService`; readiness polling through `DescribeExpressGatewayService`; optional steady-state polling through `ListServiceDeployments` and `DescribeServiceDeployments` | AWS's authorization reference lists the composite dependent actions for `CreateExpressGatewayService`, including cluster/gateway/task-definition operations, tagging, and `iam:PassRole`. The caller must not gain ALB or Auto Scaling permissions because the ECS infrastructure role owns those side effects. |
| Read / refresh | `DescribeExpressGatewayService`; the provider also calls EC2 `DescribeSecurityGroups` to filter ECS-managed security groups returned in the service network configuration | Scope the ECS describe to the service; determine whether the EC2 helper can use exact security-group ARNs or must be omitted from the apply identity and performed only by observation. Confirm shared helper and tagging framework calls before authorizing the role. |
| Update | `UpdateExpressGatewayService`; `DescribeExpressGatewayService`; optional `ListServiceDeployments` and `DescribeServiceDeployments` polling | Use the AWS `UpdateExpressGatewayService` dependent-action list and bind service, cluster, subnet, CPU/memory, and passed-role conditions to trusted plan values. |
| Delete | `DeleteExpressGatewayService`; `DescribeExpressGatewayService` polling until inactive | Use a separately approved destroy plan and deletion-only session; do not reuse create/update permissions or infer deletion from the prior create approval. |

This is provider-source evidence for the ECS API path, not a complete role
policy. The resource also invokes shared provider helpers for service lookup
and deployment status, plus the generic tag synchronization layer. Their API
actions, resource/condition support, and the provider's exact treatment of
tags still need to be mapped before permissions can be implemented. The
6.73.0 provider source does not remove the need for a fresh review when the
lockfile changes.
