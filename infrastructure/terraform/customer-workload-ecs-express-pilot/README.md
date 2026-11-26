# Same-account customer workload pilot: ECS Express Mode

This root is the new-customer workload path for the owner-controlled pilot.
AWS closed App Runner to new customers on April 30, 2026 and recommends ECS
Express Mode for new containerized web workloads. See the
[AWS availability notice](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)
and the [ECS Express Mode overview](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html).

**State: direct same-account pilot evidence is recorded in
`docs/test/test437.md`; Nova renderer execution is not enabled.** This root
supports an empty S3 backend for a project-scoped state bucket in the customer
account, with S3-native lock files. The direct pilot uses `terraform init -backend=false`
and local state. Neither mode uses the DavDeploy control-plane state bucket,
lock table, hosted API, worker, or runtime.

The root creates a dedicated customer VPC, two public subnets, an internet
gateway, and a private ECR repository. It reads the task execution and
infrastructure roles provisioned once for this DavDeploy connection by the
customer-side template in `infrastructure/cloudformation/customer-ecs-express-roles.yaml`.
Terraform does not create IAM roles or attach policies. When
`enable_service=true`, ECS Express Mode provisions a single-task Fargate
service, HTTPS load balancer, target group, service security group, scaling
configuration, certificate, and service logs. No NAT gateway or customer task
role is created. The service may access the public test endpoint; this
same-account VPC is not cross-account isolation.

The minimum task count is one and maximum is one. The ECS infrastructure role
uses the AWS managed `AmazonECSInfrastructureRoleforExpressGatewayServices`
policy; the task execution role uses `AmazonECSTaskExecutionRolePolicy`. The
runner checks each role's exact connection-specific name, service trust,
managed-policy attachment, and absence of inline policies before Terraform
operations. The container receives no AWS permissions because the task role is
omitted.

## Operator flow

Use the verified customer AWS profile and keep input variables outside Git.
The exact account and Region are checked before any resources are created.

1. As an authorized customer account administrator, deploy the published
   CloudFormation template URL exposed as
   `customer_ecs_express_roles_template_url` by the template-host Terraform
   root. Use stack name
   `davdeploy-ecs-express-roles-<connection-id>` and parameter
   `ConnectionId=<connection-id>`. The template creates exactly two
   connection-scoped roles; it does not create or broaden the DavDeploy
   customer-execution role.
2. Confirm the CloudFormation stack reaches `CREATE_COMPLETE`, allow IAM role
   propagation to settle, and use the runner's role-profile check before
   planning the workload.
3. Create a temporary tfvars file with `region`, `expected_account_id`,
   `connection_id`, `project_id`, `source_repository`, `source_commit`, and
   `plan_digest`.
   Do not put credentials or secret values in it.
4. Run `terraform init -backend=false`, review a saved foundation plan, and
   apply it through `scripts/terraform_run_monitor.py`. This creates the ECR
   repository and customer foundation using local state.
5. Build the test fixture in `../../../tests/fixtures/customer-ecs-express-health`,
   push it to the new ECR repository with an immutable tag, and record the image
   digest. Do not use a mutable `latest` tag.
6. Review a second plan with `enable_service=true` and
   `image_identifier=<repository>@<sha256-digest>`. Apply the exact saved plan
   through the run monitor. ECS Express Mode waits for steady state.
7. Read the `ingress_paths` output and verify `/healthz` returns the expected
   JSON response. Record service readiness and the exact image digest.
8. To clean up, review a saved destroy plan for this local state, obtain the
   required authorization, and apply that saved destroy plan through the run
   monitor. Verify the ECS Express service, ECR repository, customer VPC, and
   log group are absent with independent AWS reads. The two connection-scoped
   IAM roles remain available for other projects on that connection and are
   checked as retained by `verify-cleanup`.

The renderer remains disabled, and its customer-owned remote-state path has
not been used. The earlier direct pilot used local state and was destroyed.
Terraform `removed` blocks detach the former project-scoped role resources and
policy attachments from state with `destroy = false`; they do not delete the
AWS roles. Review any service-role ARN change in the saved plan. The runner's
cleanup verifier fails if either legacy role remains, so it cannot report
complete workload cleanup while legacy roles are still present.

Do not delete the connection's role-bootstrap CloudFormation stack while any
ECS Express project under that connection is active. During connection
offboarding, first destroy every workload and independently verify those
resources are absent; only then delete the bootstrap stack and independently
verify the two role names are absent. IAM role stacks do not incur a per-role
charge, but retaining them preserves the connection's deployment capability.

The ECS Express service provisions AWS-managed load balancing and a Fargate
service. These underlying resources are billable while they exist, including
the load balancer, the one running Fargate task, public IPv4 addresses, logs,
and data transfer. ECS Express Mode itself has no separate service fee; see
[Fargate pricing](https://aws.amazon.com/fargate/pricing/) and
[Elastic Load Balancing pricing](https://aws.amazon.com/elasticloadbalancing/pricing/).

Workload resources are named from a hash of the connection, project, and region
and tagged with the project ID, source commit, and plan digest. The service
roles are connection-scoped and are not deleted during an individual project
cleanup. A future renderer runner uses the customer-owned S3 bucket supplied
for that customer. It
requires bucket versioning, all S3 public-access blocks,
bucket-owner enforcement, and SSE-KMS with a customer key in the selected
account and Region. The project-scoped state key is:
`davdeploy/customer/<connection>/projects/<project>/regions/<region>/ecs-express.tfstate`.
Saved plans and run results use the separately configured artifact store.
Saved plans may contain sensitive configuration and require restricted,
encrypted storage; temporary credential files are not uploaded.

Run static checks with `make terraform-validate`. See
[the same-account boundary](../../../docs/architecture/same-account-pilot.md).
