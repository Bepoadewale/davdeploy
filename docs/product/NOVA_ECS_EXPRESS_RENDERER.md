# Nova ECS Express renderer package

## Objective

Connect the existing bounded ECS Express customer-sandbox profile to Nova's
checked-in lifecycle renderer contract. AWS currently recommends ECS Express
Mode for managed container web applications; the repository already has an
isolated Terraform root and direct create, health, update, rollback, and cleanup
evidence in `docs/test/test437.md`.

## Boundaries

- This package is limited to the existing single-service ECS Express profile.
- The broad `aws-ecs-fargate` planning profile must not be routed to this
  single-container pilot renderer. The pilot has its own catalogue identifier.
- It must use the exact saved plan and project-scoped remote-state paths used by
  the execution runner; the direct pilot's local state remains an isolated test
  mode.
- Images must be pinned by digest. Health must be checked against the returned
  service URL and expected application contract.
- Apply and destroy remain gated until the runner contract, IAM bounds, plan
  policy, cost evidence, and isolated lifecycle verification are complete.
- No hosted control-plane deployment or mutation is part of this package.
- A direct same-account lifecycle result remains distinct from Nova-originated
  execution and cross-account evidence.

## Acceptance

The renderer must have a fixed Terraform root and command map, reject unknown
operations and malformed tenant/run bindings, verify the exact saved-plan
digest before execution, return bounded non-secret evidence, verify application
readiness independently, and prove resource absence after authorized cleanup.
Regression tests must cover rejection and success contracts. Any paid cloud
cycle requires a fresh resource manifest, current quota and price preflight,
runtime and cost bounds, monitored Terraform operations, and independent
absence checks.

## Current status

Draft PR #519 implements the fixed ECS Express renderer contract, project-
scoped Terraform root, and bounded runner. The renderer remains disabled.
Merged PR #520 adds exact-shape actual-plan checks, and merged PR #522 adds
regional pricing for the model's material ECS Express usage dimensions. The
provider-generated pilot plan has been checked under those policies, but its
pricing evidence used synthetic persisted context and no customer budget, so it
cannot authorize a customer run. Effective runner-role permissions and the
project-scoped remote-state lifecycle remain unverified.

The existing same-account lifecycle result in `docs/test/test437.md` is accepted
as the isolated customer deployment test while the hosted control plane remains
untouched. It does not prove Nova-originated dispatch or cross-account
isolation. The new runner still requires its own local clean-room and isolated
remote-state cycles before it can be enabled.

## Research

- [Amazon ECS Express Mode](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html)
- [ECS infrastructure IAM role and `iam:PassRole`](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/infrastructure_IAM_role.html)
- [AWS managed ECS Express infrastructure policy](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonECSInfrastructureRoleforExpressGatewayServices.html)
- [HashiCorp AWS provider: `aws_ecs_express_gateway_service`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_express_gateway_service)
- [Existing lifecycle evidence](../test/test437.md)
