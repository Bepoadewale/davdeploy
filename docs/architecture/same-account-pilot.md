# Same-account platform and customer-sandbox pilot

The controlled pilot uses one AWS account because the repository owner has
explicitly prohibited creation of AWS Organizations member accounts. It uses
separate placement contracts inside account `654654474502`:

| Placement | Scope tag | VPC CIDR | Terraform state key |
| --- | --- | --- | --- |
| davdeploy platform | `platform` | `10.42.0.0/16` | `davdeploy/platform/app-runner-runtime.tfstate` |
| Customer sandbox | `customer-sandbox` | `10.84.0.0/16` | local state for the ECS Express Mode pilot |

Both placements carry `AccountBoundary=same-account-pilot`. The customer
sandbox output states `SAME_ACCOUNT_PILOT_NOT_CROSS_ACCOUNT`; UI, audit and test
evidence must preserve that limitation.

## Enforced boundaries

- Exact account and Region checks run before Terraform operations.
- Platform and customer resources use different names, VPCs, subnets, security
  groups, IAM roles, tags and state keys.
- The ECS Express customer test has a dedicated VPC with two public subnets and
  an internet gateway. It has no NAT gateway. ECS Express Mode creates the
  service load balancer, task security group, Fargate service and scaling
  resources for the test.
- The task has no AWS task role. Separate execution and infrastructure roles
  use the AWS managed policies required by ECS Express Mode.
- Destructive commands require exact confirmation text.
- Customer teardown verifies absence of its ECS Express service, ECR repository,
  tagged VPC and named roles.
- No automation creates or invites an AWS Organizations account.

AWS closed App Runner to new customers on April 30, 2026. The App Runner pilot
root is retained as a historical design; new customer pilots use
[ECS Express Mode](../../infrastructure/terraform/customer-workload-ecs-express-pilot/README.md).

## What this does not prove

A VPC is a network boundary, not an AWS account boundary. Platform and customer
resources still share the same account administrator, service quotas, billing,
CloudTrail administration and ultimate IAM control. This pilot is suitable for
owner-controlled design-partner evidence only. It must not be described as
cross-account tenant isolation or used as the long-term boundary for unrelated
customers.

## Operator variables

```text
EXPECTED_AWS_ACCOUNT_ID=654654474502
AWS_REGION=us-east-1
DAVDEPLOY_PLATFORM_SCOPE=platform
DAVDEPLOY_PLATFORM_VPC_CIDR=10.42.0.0/16
DAVDEPLOY_CUSTOMER_DEPLOYMENT_SCOPE=customer-sandbox
DAVDEPLOY_CUSTOMER_VPC_CIDR=10.84.0.0/16
```

Account creation, Organization invitation and account deletion are outside the
pilot scripts. Deleting the customer sandbox means running its bounded Terraform
destroy and absence verification; it does not mean deleting the shared AWS
account.
