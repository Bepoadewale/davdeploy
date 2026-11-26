# Nova ECS Express renderer package

## Objective

Connect the existing bounded ECS Express customer-sandbox profile to Nova's
checked-in lifecycle renderer contract. AWS currently recommends ECS Express
Mode for managed container web applications; the repository already has an
isolated Terraform root and direct create, health, update, rollback, and cleanup
evidence in `docs/test/test437.md`.

## Boundaries

- This package is limited to the existing single-service ECS Express profile.
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

Queued for implementation on a focused PR. The existing direct ECS Express
evidence is same-account AWS evidence; it does not demonstrate the new Nova
renderer path.

## Research

- [Amazon ECS Express Mode](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html)
- [HashiCorp AWS provider: `aws_ecs_express_gateway_service`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_express_gateway_service)
- [Existing lifecycle evidence](../test/test437.md)
