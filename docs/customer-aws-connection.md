# Connect an AWS account

davdeploy starts with a read-only connection. It does not ask for AWS access keys or administrator access.

## Connect for discovery

1. In davdeploy, choose **Connect AWS account** and enter the 12-digit AWS account ID.
2. Select **Open AWS setup**.
3. In the AWS Console, review one CloudFormation stack, acknowledge IAM resource creation, and choose **Create stack**.
4. Return to davdeploy and select **Verify connection**. davdeploy queues a read-only check. Its runtime identity assumes the role for 15 minutes, reads infrastructure metadata, and stores a credential-free inventory snapshot.

The customer does not create an IAM user, write a discovery policy, install Terraform, run a command, or copy AWS credentials.

## What AWS creates

The template creates one `davdeployDiscovery-*` IAM role. It is allowed to read infrastructure metadata and Cost Explorer data only. It cannot create, update, delete, pass roles, read S3 objects, read database contents, or retrieve secret values.

The trust policy requires davdeploy's API role and one unique external ID. Sessions are short-lived. The ExternalId is held in the control-plane secret store and is also passed to CloudFormation in the Quick Create URL so the customer stack can set the trust condition. Treat the setup URL as sensitive until the stack is created. The role can be removed to disconnect the account.

## Add the Nova plan-only role

After discovery is verified, choose the `plan-only` Quick Create option for the same account. It creates a separate `davdeploy-Plan-*` stack and role; it leaves the discovery stack intact and reuses the connection ExternalId. The role trusts the API verification role and the separately isolated Nova plan broker. It has an explicit deny for every customer service action and no service Allow policy.

The current Nova Terraform runner can use this role for an initial backend-free plan that checks only AWS account identity. It cannot refresh existing state or inspect service data. Verification confirms role assumption and account identity; it does not reread effective IAM policy, so customer changes to the role after setup are not detected.

The isolated Nova broker ARN must be configured before the API can generate this setup link. New broker AssumeRole permissions and the API verification permission for `davdeployPlan-*` are follow-up work; this change does not broaden the existing customer executor.

## Product boundary

The Quick Create endpoint only generates an AWS Console link. The customer creates the stack in their own account. The browser never receives AWS credentials. The plan-only role cannot provision a workload. A separately approved execution role is still required for the existing App Runner deployment path.

For local development, set `DAVDEPLOY_CONTROL_PLANE_ROLE_ARN`, `DAVDEPLOY_AWS_CONNECTION_TEMPLATE_URL`, and the explicit live-discovery flag only outside Git. Plan-only role setup and identity verification are disabled by default; hosted Terraform enables them separately with `enable_nova_plan_role_verification=true`. This grants the API `sts:AssumeRole` only for customer roles named `davdeployPlan-*`, requiring a non-empty connection ExternalId and the plan-verification session-name prefix. The plan-only Quick Create flow works while the isolated runner remains disabled: its CloudFormation trust omits the optional runner principal. When the runner is enabled, Terraform wires its CodeBuild role ARN into the template; that runner remains fail-closed until its implementation is validated. A `VERIFIED` plan role means trust and AWS account identity were checked only. Its effective permissions remain `POLICY_UNATTESTED`; DavDeploy does not inspect or attest the customer's installed policy. Production uses separate runtime roles, not the GitHub Actions role. Use `DAVDEPLOY_CONNECTION_SECRET_BACKEND=aws_secrets_manager` in hosted environments; `local_encrypted` is only a local substitute. The template URL must be a public, versioned S3 object with no customer data or secrets; a private repository raw URL is not suitable. The Terraform template-host root is applied and verified. The App Runner runtime root is also applied for read-only discovery validation, with fixture sign-in/policy and ephemeral SQLite still clearly labeled non-production.

## Current hosted validation

On 2026-10-13, the AWS-hosted davdeploy runtime at `https://x75qgwappp.us-east-1.awsapprunner.com` created a Quick Create URL, assumed the resulting customer read-only discovery role with STS, and stored a credential-free inventory snapshot with `live-read-only-sts-discovery` provenance. The temporary customer CloudFormation stack, discovery role and per-connection ExternalId secret were deleted after verification. No customer workload resources were created.

Current hosted template URL:

```text
https://davdeploy-customer-templates-654654474502.s3.us-east-1.amazonaws.com/cloudformation/customer-discovery-role-0e3209bff02286acf582ec3ed73858266261b294ae0c7e0d30ae37550a8926b2.yaml
```
