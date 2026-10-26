# ticket171 — Activate Resend invitations without Terraform secret state

PR: [#171](https://github.com/Bepoadewale/davdeploy/pull/171)
Branch: `feat/resend-runtime-parameter`

## Problem / goal

Enable the verified Resend sender for hosted workspace invitations while keeping its API key outside source control, GitHub workflow logs, Lambda environment variables, and Terraform state.

## Current repo state

Resend delivery is implemented but deliberately disabled in the hosted runtime. The sender domain is verified and the existing key has been proven to send mail, but it cannot safely be supplied through Terraform as a secret input.

## Research / references used

- The existing Resend adapter and Amazon SES hosted-delivery boundary in local source code.
- AWS Systems Manager Parameter Store Standard SecureString behavior.
- The protected serverless-control-plane Terraform plan workflow.

## Work planned for the PR

- Store the sending-only Resend key as one AWS Systems Manager Parameter Store **Standard SecureString**.
- Pass only its non-secret name through the protected Terraform-plan environment.
- Classify that non-secret environment variable in the repository’s Actions configuration policy.
- Grant the hosted API role read access only to that exact parameter.
- Resolve and cache the key at runtime, then use the existing Resend invitation adapter.

## Acceptance criteria

- [x] No Resend key is added to source control, Terraform variables, Terraform state, or Lambda environment variables.
- [x] The hosted API role can read only the configured parameter.
- [x] The hosted runtime selects Resend only when the parameter name is configured.
- [x] Local backend and Terraform validation pass.

## Acceptance status

Local acceptance is met. Production activation waits for protected Terraform plan/apply review.

## Tests / validation performed

See `docs/test/test171.md`.

## Evidence files produced

- `docs/test/test171.md`

## Cost and boundaries

Standard Parameter Store storage is free. This does not enable customer workload execution, change inbound mail routing, or create an AWS Secrets Manager secret.

## Boundaries

No production Lambda configuration or invitation is changed by this pull request alone; the existing manual Terraform deployment gate remains required.

## Follow-up work

Review and apply the protected production Terraform plan, then create one controlled workspace invitation and confirm delivery.

