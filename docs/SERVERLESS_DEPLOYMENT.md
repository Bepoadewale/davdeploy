# Serverless control-plane deployment

## Target architecture

The hosted control plane uses API Gateway HTTP API, Python Lambda, Aurora PostgreSQL Serverless v2 through RDS Data API, Cognito, SQS, an isolated policy Lambda, Amazon Nova 2 Lite, and Resend for workspace invitations. Lambda is not attached to the database VPC. The database subnets have no Internet Gateway or NAT Gateway.

This is the production deployment contract. Manual Terraform plan/apply remains deliberately outside routine tests and requires the protected GitHub environments.

## Release sequence

1. Build `dist/lambda/davdeploy-control-plane.zip` with `bash scripts/build_lambda_packages.sh` on Amazon Linux or the CI packaging image. Native dependencies must target Lambda Python 3.12, not macOS.
2. Upload the immutable zip to an existing versioned private S3 artifact bucket.
3. Configure the single production remote Terraform state and reviewed inputs for `infrastructure/terraform/serverless-control-plane`.
4. Run `terraform plan` and review exact cost, IAM, deletion-protection, origin, region, and artifact inputs.
5. Without changing `main`, apply only through the guarded operator workflow after explicit
   approval. The workflow resolves the newest successful plan for that exact commit automatically.
6. The apply workflow invokes the emitted migration Lambda and requires `migrations-complete` before reporting success. A migration failure fails the release.
7. Configure Google federation using the operator's local secret source. Do not pass the Google client secret through Terraform because it would be retained in Terraform state.
8. Set `google_identity_provider_enabled = true`, plan, and apply the Cognito app-client update.
9. Set the frontend's public Cognito and API variables in Cloudflare Pages and redeploy static assets.
10. Run live Google, email OTP, invitation acceptance, tenant onboarding, authorization denial, API, worker retry, policy failure, backup, restore, and teardown smoke tests.

## Google identity provider

Create a Google OAuth web client with Cognito's generated `/oauth2/idpresponse` URL as an exact authorized redirect URI. Store the secret in macOS Keychain under `davdeploy-google-oauth-client-secret`, set `COGNITO_USER_POOL_ID` and `GOOGLE_CLIENT_ID`, then run `bash scripts/configure_cognito_google.sh`. The script requests only `openid email profile`, uses a mode-600 temporary payload, and removes it on exit. The secret must never be committed, logged, placed in a `VITE_*` variable, or written to Terraform state.

The pre-sign-up Lambda links Google to an existing native Cognito account only when Google supplies a verified email. davdeploy still resolves organization and role from its own database.

## Email OTP

Cognito choice-based `USER_AUTH` and `EMAIL_OTP` require an eligible Cognito feature plan and
Amazon SES delivery. Cognito is configured with the verified `davdeploy.tech` SES identity and
`notify@davdeploy.tech` sender. The SES account remains sandboxed until AWS approves the submitted
transactional-production request; until then, OTP delivery is limited to verified SES recipients.
Resend remains the separate workspace-invitation sender.

## Workspace invitations

The deployed API uses Resend for workspace invitations, from `DavDeploy <notify@davdeploy.tech>`
with `support@davdeploy.tech` as Reply-To. The verified sending key is held as a Standard SSM
SecureString and is fetched only by the API role at runtime. Cloudflare Email Routing handles
inbound forwarding separately; it is not a transactional email provider.

## Required frontend values

- `VITE_API_BASE_URL`: API Gateway output `api_base_url`
- `VITE_AUTH_MODE=oidc`
- `VITE_OIDC_AUTHORITY`: output `cognito_issuer`
- `VITE_OIDC_CLIENT_ID`: output `cognito_client_id`
- `VITE_COGNITO_REGION`: Terraform region
- `VITE_COGNITO_USER_POOL_CLIENT_ID`: output `cognito_client_id`
- exact Pages callback and logout URLs

All are public identifiers. None is a credential.

## Cost and safety boundaries

- Aurora Serverless v2 is configured to auto-pause at zero capacity after 15 idle minutes. Storage, requests, snapshots and active capacity still incur charges, and the first request after pause has resume latency.
- API Gateway, Lambda, SES, SQS, CloudWatch logs, Cognito beyond its allowance, Bedrock, Secrets Manager and data transfer can incur charges.
- AWS Budget is alerting, not a hard spending cap.
- Database deletion protection and final snapshots are enabled by default.
- The stack does not create customer workload resources.
- The current workflow deploys one production control plane. It has no development or staging
  selector and uses `serverless-control-plane/terraform.tfstate` as its only state object.
