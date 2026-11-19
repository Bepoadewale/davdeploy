# Same-account customer workload pilot: ECS Express Mode

This root is the new-customer workload path for the owner-controlled pilot.
AWS closed App Runner to new customers on April 30, 2026 and recommends ECS
Express Mode for new containerized web workloads. See the
[AWS availability notice](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)
and the [ECS Express Mode overview](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html).

**State: design only until an authorized account-side run is recorded in the
linked test evidence. This root uses local Terraform state and does not use the
DavDeploy platform state bucket, lock table, hosted API, worker, or runtime.**

The root creates a dedicated customer VPC, two public subnets, an internet
gateway, a private ECR repository, an ECS task execution role, and an ECS
infrastructure role. When `enable_service=true`, ECS Express Mode provisions a
single-task Fargate service, HTTPS load balancer, target group, service security
group, scaling configuration, certificate, and service logs. No NAT gateway or
customer task role is created. The service may access the public test endpoint;
this same-account VPC is not cross-account isolation.

The minimum task count is one and maximum is one. The ECS infrastructure role
uses the AWS managed `AmazonECSInfrastructureRoleforExpressGatewayServices`
policy; the task execution role uses `AmazonECSTaskExecutionRolePolicy`. The
container receives no AWS permissions because the task role is omitted.

## Operator flow

Use the verified customer AWS profile and keep input variables outside Git.
The exact account and Region are checked before any resources are created.

1. Create a temporary tfvars file with `region`, `expected_account_id`,
   `connection_id`, `source_repository`, `source_commit`, and `plan_digest`.
   Do not put credentials or secret values in it.
2. Run `terraform init -backend=false`, review a saved foundation plan, and
   apply it through `scripts/terraform_run_monitor.py`. This creates the ECR
   repository and customer foundation using local state.
3. Build the test fixture in `../../../tests/fixtures/customer-ecs-express-health`,
   push it to the new ECR repository with an immutable tag, and record the image
   digest. Do not use a mutable `latest` tag.
4. Review a second plan with `enable_service=true` and
   `image_identifier=<repository>@<sha256-digest>`. Apply the exact saved plan
   through the run monitor. ECS Express Mode waits for steady state.
5. Read the `ingress_paths` output and verify `/healthz` returns the expected
   JSON response. Record service readiness and the exact image digest.
6. To clean up, review a saved destroy plan for this local state, obtain the
   required authorization, and apply that saved destroy plan through the run
   monitor. Verify the ECS Express service, ECR repository, test roles, and
   customer VPC are absent with independent AWS reads.

The ECS Express service provisions AWS-managed load balancing and a Fargate
service. These underlying resources are billable while they exist, including
the load balancer, the one running Fargate task, public IPv4 addresses, logs,
and data transfer. ECS Express Mode itself has no separate service fee; see
[Fargate pricing](https://aws.amazon.com/fargate/pricing/) and
[Elastic Load Balancing pricing](https://aws.amazon.com/elasticloadbalancing/pricing/).

Run static checks with `make terraform-validate`. See
[the same-account boundary](../../../docs/architecture/same-account-pilot.md).
