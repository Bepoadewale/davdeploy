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
- `TF_PLAN_BUCKET`
- `TF_PLAN_KMS_KEY_ARN`
- `TF_RELEASE_BUCKET`
- `TF_RELEASE_KMS_KEY_ARN`
- `TF_STATE_BUCKET`
- `TF_STATE_LOCK_TABLE`

These values identify deployment configuration. They do not authenticate a caller and remain
GitHub Actions variables. Bucket policies, IAM trust policies, KMS policies, branch restrictions,
and environment protections provide authorization.

The current encrypted environment values are:

- `BUDGET_NOTIFICATION_EMAIL`, stored as a `terraform-plan` environment secret.
- `SES_IDENTITY_ARN` and `SES_FROM_ADDRESS`, stored as `terraform-plan` environment secrets.
- `RESEND_INVITATION_PARAMETER_NAME`, stored as a `terraform-plan` environment variable. This is
  only the name of a Standard SSM SecureString; the Resend value itself is read by the hosted
  Lambda runtime and is never a GitHub variable, secret, Terraform input, or Lambda environment value.

Hosted workspace invitation delivery uses the verified Resend domain. The API role receives only
`ssm:GetParameter` on the exact configured parameter, retrieves it with decryption at runtime, and
does not receive the key as a Lambda environment variable. SES settings remain optional for a future
Cognito delivery path; they are not the invitation sender. The backend stores token digests, never
raw invitation tokens, and hosted API responses never expose invitation links.

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
