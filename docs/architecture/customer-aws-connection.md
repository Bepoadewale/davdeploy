# Customer AWS connection

davdeploy connects to a customer AWS account in stages. The first stage is discovery only.

## What the first role can do

The Terraform contract creates a discovery role with short-lived STS access. It can list and describe approved AWS infrastructure and ask Cost Explorer for cost information. It can inspect services such as VPCs, App Runner, ECS, EKS, Lambda, RDS, ElastiCache, ECR and bucket metadata.

It cannot create, change or delete infrastructure. It cannot read Secrets Manager values, S3 object contents, container images, application logs or database data. It does not create an access key.

## Optional Nova plan-only role

After the discovery connection is verified, an administrator can create a separate `davdeployPlan-*` role through Quick Create. It is installed as a second CloudFormation stack so it does not replace the discovery stack. The role trusts the configured API verification role and future isolated Nova plan broker, and requires the same per-connection ExternalId.

The template attaches an explicit deny for every customer service action and grants no service permissions. The current Nova runner can still produce an initial backend-free plan because it only needs AWS account identity. It cannot refresh existing Terraform state, inspect data sources, or plan updates against existing state. Those capabilities need a reviewed read policy before they are enabled.

Role verification proves that STS can assume the role and that its caller identity belongs to the connected account. It does not inspect effective IAM permissions or detect later customer edits to the policy.

## Trust boundary

Discovery and plan roles require the connection's unique external ID. The discovery role trusts the API broker. The plan role trusts the API broker for verification and a separately isolated Nova plan broker for planning. Broker `sts:AssumeRole` permissions for `davdeployPlan-*` are a follow-up; this change does not broaden the existing customer executor.

The ExternalId stays in the control-plane secret store, but Quick Create includes it in the AWS Console URL so CloudFormation can write the trust condition. Treat that link as sensitive until the role is installed. It is not an AWS access key or customer workload credential.

An authenticated plan needs the exact ARN of the isolated Nova plan broker. The setup path fails closed until that role ARN is configured. Verifying the customer plan role also needs the API broker's new `sts:AssumeRole` permission for `davdeployPlan-*`; that permission is a follow-up change.

The browser, CLI and MCP server never receive STS session credentials. The setup URL contains the ExternalId so CloudFormation can install the trust condition; treat the URL as sensitive. Only the governed control plane or isolated plan broker can request a short-lived role session after tenant, account and policy checks.

## Current state

**Plan role not yet live:** the customer template and API can prepare and verify the role contract, but the isolated broker's customer-role assumption and the API verification permission are not part of this change.

**Not executed:** an authenticated AWS plan, IAM role creation, STS assumption, inventory discovery, Cost Explorer query or any customer workload change.
