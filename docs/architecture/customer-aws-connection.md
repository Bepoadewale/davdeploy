# Customer AWS connection

davdeploy connects to a customer AWS account in stages. The first stage is discovery only.

## What the first role can do

The Terraform contract creates a discovery role with short-lived STS access. It can list and describe approved AWS infrastructure and ask Cost Explorer for cost information. It can inspect services such as VPCs, App Runner, ECS, EKS, Lambda, RDS, ElastiCache, ECR and bucket metadata.

It cannot create, change or delete infrastructure. It cannot read Secrets Manager values, S3 object contents, container images, application logs or database data. It does not create an access key.

## Optional Nova plan-only role

After the discovery connection is verified, an administrator can create a separate `davdeployPlan-*` role through Quick Create. It is installed as a second CloudFormation stack so it does not replace the discovery stack. The role trusts the control-plane role, which performs role verification and run-scoped plan credential brokerage, and requires the same per-connection ExternalId. CodeBuild receives credentials only through the authenticated broker route for its exact active build.

The template attaches an explicit deny for every customer service action and grants no service permissions. The current Nova runner can still produce an initial backend-free plan because it only needs AWS account identity. It cannot refresh existing Terraform state, inspect data sources, or plan updates against existing state. Those capabilities need a reviewed read policy before they are enabled.

Role verification proves that STS can assume the role and that its caller identity belongs to the connected account. It does not inspect effective IAM permissions or detect later customer edits to the policy.

## Trust boundary

Discovery and plan roles require the connection's unique ExternalId. Both trust the control-plane role. For Nova planning, the API derives the build ID from the authenticated CodeBuild role session, then verifies the durable run, active build, immutable revision and proposal before assuming the exact plan role with a proposal-scoped explicit-deny session policy. The broker request contains only a run ID; callers cannot select a build ID. CodeBuild has no customer-role `sts:AssumeRole` permission.

The ExternalId stays in the control-plane secret store, but Quick Create includes it in the AWS Console URL so CloudFormation can write the trust condition. Treat that link as sensitive until the role is installed. It is not an AWS access key or customer workload credential.

An authenticated plan needs the exact fixed CodeBuild project and its IAM-authenticated broker route. The route and broker are disabled by default. The API's plan-role assumption permission is separately gated for verification and credential brokerage.

The browser, CLI and MCP server never receive STS session credentials. The setup URL contains the ExternalId so CloudFormation can install the trust condition; treat the URL as sensitive. Only the governed control plane can request a short-lived role session after tenant, account, active-build and policy checks.

## Current state

**Hosted plan credential brokerage remains disabled:** source includes the run-scoped broker and control-plane-only trust contract, but the feature has not been deployed or enabled. Customer role installation and effective permissions remain unverified.

**Not executed:** an authenticated AWS plan, IAM role creation, STS assumption, inventory discovery, Cost Explorer query or any customer workload change.
