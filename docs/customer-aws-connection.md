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

After discovery is verified, a workspace administrator can choose the `plan-only` Quick Create option for the same account when `enable_nova_plan_role_verification=true`. It creates a separate `davdeploy-Plan-*` stack and role; it leaves the discovery stack intact and reuses the connection ExternalId. The role always trusts the API verification role. It trusts the isolated Nova runner broker only when that runner is enabled; otherwise the broker principal is omitted.

The CloudFormation template attaches an expected explicit deny for customer service actions, but DavDeploy does not verify effective IAM permissions. A successful verification proves only role trust and account identity; policy status remains `POLICY_UNATTESTED`, and later customer policy changes are not detected. The current Nova CodeBuild project is a fail-closed stub; no Nova-generated plan has been run through it.

The verification flag defaults off and can be enabled while the runner remains off. In the protected GitHub Actions `terraform-plan` environment, its variable is named `NOVA_PLAN_ROLE_VERIFICATION_ENABLED`; if unset, the workflow passes `false` to Terraform. Keep it unset or `false` in hosted AWS until verification is deliberately enabled. When enabled, the API may assume roles named `davdeployPlan-*` only, with a connection ExternalId and dedicated verification session name. Terraform supplies the optional broker ARN from the CodeBuild role only when the runner is enabled. This change does not broaden the existing customer executor.

## Product boundary

The Quick Create endpoint only generates an AWS Console link. The customer creates the stack in their own account. The browser never receives AWS credentials. The plan-only role's effective permissions are not attested, and the current runner cannot execute plans. A separately approved execution role is still required for the existing App Runner deployment path.

For local development, set `DAVDEPLOY_CONTROL_PLANE_ROLE_ARN`, `DAVDEPLOY_AWS_CONNECTION_TEMPLATE_URL`, and the explicit live-discovery flag only outside Git. Plan-only role setup and identity verification are disabled by default; hosted Terraform enables them separately with `enable_nova_plan_role_verification=true`. This grants the API `sts:AssumeRole` only for customer roles named `davdeployPlan-*`, requiring a non-empty connection ExternalId and the plan-verification session-name prefix. The plan-only Quick Create flow works while the isolated runner remains disabled: its CloudFormation trust omits the optional runner principal. When the runner is enabled, Terraform wires its CodeBuild role ARN into the template; that runner remains fail-closed until its implementation is validated. A `VERIFIED` plan role means trust and AWS account identity were checked only. Its effective permissions remain `POLICY_UNATTESTED`; DavDeploy does not inspect or attest the customer's installed policy. Production uses separate runtime roles, not the GitHub Actions role. Use `DAVDEPLOY_CONNECTION_SECRET_BACKEND=aws_secrets_manager` in hosted environments; `local_encrypted` is only a local substitute. The template URL must be a public, versioned S3 object with no customer data or secrets; a private repository raw URL is not suitable. The Terraform template-host root is applied and verified. The App Runner runtime root is also applied for read-only discovery validation, with fixture sign-in/policy and ephemeral SQLite still clearly labeled non-production.

## Current hosted validation

On 2026-10-13, the AWS-hosted davdeploy runtime at `https://x75qgwappp.us-east-1.awsapprunner.com` created a Quick Create URL, assumed the resulting customer read-only discovery role with STS, and stored a credential-free inventory snapshot with `live-read-only-sts-discovery` provenance. The temporary customer CloudFormation stack, discovery role and per-connection ExternalId secret were deleted after verification. No customer workload resources were created.

Current hosted template URL:

```text
https://davdeploy-customer-templates-654654474502.s3.us-east-1.amazonaws.com/cloudformation/customer-discovery-role-f3d9e1e5776fe147bbbc10107e41d221497f9b98c6b641eb8ac08467fd54aedb.yaml
```
