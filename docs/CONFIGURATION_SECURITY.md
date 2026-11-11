# Configuration security

This repository is public. GitHub repository and environment Settings are not readable by an
anonymous visitor, but Actions variables are still unencrypted configuration and render unmasked
if a workflow prints them. They must never contain credentials or confidential data.

## Classification

The current Terraform environments use these non-secret variables:

- `AWS_REGION`
- `AWS_TERRAFORM_APPLY_ROLE_ARN`
- `AWS_TERRAFORM_PLAN_ROLE_ARN`
- `COGNITO_DOMAIN_PREFIX`
- `EXPECTED_AWS_ACCOUNT_ID`
- `FRONTEND_ORIGIN`
- `GOOGLE_IDENTITY_PROVIDER_ENABLED`
- `NOVA_PLAN_ONLY_RUNNER_ENABLED`
- `NOVA_PLAN_ROLE_VERIFICATION_ENABLED`
- `NOVA_TERRAFORM_STATE_API_ENABLED`
- `NOVA_TERRAFORM_STATE_API_URL`
- `NOVA_TERRAFORM_STATE_STORAGE_ENABLED`
- `SERVERLESS_API_HOSTED_CERTIFICATION_ENABLED`
- `SERVERLESS_CERTIFICATION_WORKSPACE_IDS_JSON`
- `TF_PLAN_BUCKET`
- `TF_PLAN_KMS_KEY_ARN`
- `TF_RELEASE_BUCKET`
- `TF_RELEASE_KMS_KEY_ARN`
- `TF_STATE_BUCKET`
- `TF_STATE_LOCK_TABLE`

These values identify deployment configuration. They do not authenticate a caller and remain
GitHub Actions variables. Bucket policies, IAM trust policies, KMS policies, branch restrictions,
and environment protections provide authorization.

`NOVA_PLAN_ONLY_RUNNER_ENABLED` defaults to `false`. When enabled, Terraform creates a separate
fixed CodeBuild project and scoped role. Its generated plans remain unapprovable while complete
regional pricing evidence is unavailable; enabling this flag alone does not authorize customer
resource changes.

`NOVA_PLAN_ROLE_VERIFICATION_ENABLED` maps to Terraform's
`enable_nova_plan_role_verification` input and defaults to `false` when unset. The protected
`terraform-plan` workflow reads this Actions variable; leave it unset or explicitly `false` in the
hosted environment until plan-role verification is deliberately enabled. This setting is separate
from the Nova runner flag and does not attest customer role permissions or enable deployment.

`NOVA_TERRAFORM_STATE_STORAGE_ENABLED` and `NOVA_TERRAFORM_STATE_API_ENABLED` both default to
`false`; `NOVA_TERRAFORM_STATE_API_URL` defaults to an empty value. The API flag is rejected by
Terraform unless the isolated Nova runner and dedicated state bucket are also enabled and the URL
is a valid HTTPS origin. These workflow mappings only pass configuration to the reviewed saved
plan. Leaving these Actions variables unset preserves the default-off behavior;
no hosted variable values are changed by this code update.

The serverless API certification inputs are off by default. Set
`SERVERLESS_API_HOSTED_CERTIFICATION_ENABLED` to `true` only for a controlled certification and
set `SERVERLESS_CERTIFICATION_WORKSPACE_IDS_JSON` to a JSON list containing only the test
workspace ID. An empty list denies all workspaces. Configure them in the protected
`terraform-plan` environment; Terraform apply consumes the exact immutable saved plan.

The current encrypted environment values are:

- `BUDGET_NOTIFICATION_EMAIL`, stored as a `terraform-plan` environment secret.
- `SES_IDENTITY_ARN` and `SES_FROM_ADDRESS`, stored as `terraform-plan` environment secrets.
- `RESEND_INVITATION_PARAMETER_NAME`, stored as a `terraform-plan` environment variable. This is
  only the name of a Standard SSM SecureString; the Resend value itself is read by the hosted
  Lambda runtime and Cognito custom-email sender at runtime. It is never a GitHub variable,
  secret, Terraform input, or Lambda environment value.

Hosted workspace invitation delivery and Cognito custom-email delivery use the verified Resend
domain. Each runtime role receives only its exact Parameter Store and KMS grants, retrieves the
key with decryption at runtime, and does not receive it as a Lambda environment variable. SES is a
fallback Cognito configuration; it is not the active invitation or one-time-code sender. The backend
stores token digests, never raw invitation tokens, and hosted API responses never expose invitation
links.

Future passwords, tokens, private keys, webhook secrets, client secrets, and long-lived
credentials must use GitHub Secrets or an external secret manager. AWS workflows continue to use
GitHub OIDC and short-lived credentials, never stored AWS access keys.

## Public frontend values

API origins, Cognito issuer URLs, Cognito public client IDs, regions, and frontend feature flags
are public browser configuration. Moving them into a GitHub Secret would only hide them during the
build because the browser bundle must contain them. Confidential provider credentials remain in
the backend and must never use a `VITE_*` variable.

## Enforcement

`python scripts/check_actions_configuration.py` allowlists every workflow `vars` and `secrets`
reference and rejects secret-like variable names. Gitleaks scans repository history separately.
Adding a new configuration name requires an explicit classification change in the same reviewed
PR.

Changing storage does not repair prior exposure. If a credential is ever committed, printed, or
shared outside its intended boundary, revoke or rotate it and then remove the exposed value.
