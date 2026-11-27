# Nova ECS Express actual-plan policy

## Objective

Add deterministic actual-plan checks for the bounded ECS Express pilot. The
checks bind the service to its planned image, roles, log group, and
project-scoped network resources, and reject unknown or unsupported shapes.

This is separate from `aws-ecs-fargate`, which remains a broad planning profile
for multi-container and API-worker services. The pilot is one single-container
HTTPS service with fixed compute, scaling, network, and fixture-image bounds.

## Implemented policy boundary

The evaluator applies a narrow profile contract only when an
`aws_ecs_express_gateway_service` resource occurs. It must validate the exact
resource inventory and configuration references rather than trusting labels
or Terraform addresses alone. Unsupported dependencies, unknown critical
values, unbounded role permissions, arbitrary task roles, secret injection,
mutable or external images, extra containers, scaling beyond one task, or
cross-account resources must fail closed.

The pilot uses two public subnets. AWS documents that ECS Express assigns
public task IPs by default in public subnets. The policy therefore must make
that exposure explicit and retain human review; it must not describe this
profile as private networking. Cost approval remains incomplete until Fargate,
load balancer and capacity units, public IPv4, logs, ECR storage, data transfer,
and any other material supporting charges are modeled from current regional
prices and trusted usage bounds.

The ECS Express plan remains eligible for human review only after deterministic
checks pass. Human review is required for AWS-managed supporting resources,
public task IP and internet egress, and the contents of AWS-managed role
policies. The ECR force-delete exception applies only to the exact same-plan
repository bound to the pilot service and still produces a review finding.
This source change does not prove provider-generated plan compatibility,
effective `iam:PassRole` scope, complete cost coverage, Nova dispatch, or cloud
lifecycle behavior.

## Safety boundary

This policy does not enable renderer dispatch, approve a plan, grant IAM
permissions, or declare pricing complete. A human approval remains separate
from execution. The current hosted control plane and AWS inventory are outside
this package.

## Sources

- [ECS Express resources and defaults](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html)
- [ECS Express IAM role setup](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html)
- [ECS infrastructure role and PassRole](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/infrastructure_IAM_role.html)
- [ECS IAM behavior](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security_iam_service-with-iam.html)
- [Terraform ECS Express resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_express_gateway_service)
