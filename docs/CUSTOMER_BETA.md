# Customer beta readiness

## Current launch boundary

DavDeploy is suitable only for a small, operator-supported design-partner beta. It can accept a
connected repository and AWS account, produce a governed infrastructure recommendation, preserve
review evidence, and require an independent approval. It must not be presented as an autonomous
customer-workload deployment service.

The hosted control plane is operating in `us-east-1` with Cognito identity verification, API
Gateway, Lambda functions, and Aurora PostgreSQL. This is live infrastructure, not fixture-only
evidence. Individual workflow claims remain limited to their recorded evidence.

## Entry criteria before inviting a customer

1. The worker DLQ alarm is investigated and clear. The 2026-10-28 read-only check found zero
   visible or in-flight messages, normal worker/DLQ alarms, and the corrected `bedrock` provider
   configuration. Preserve this result in the operations record; do not replay or remove messages
   without a separately approved incident decision.
2. A customer has an administrator invitation path. The deployed Resend sender is verified and
   active for workspace invitations from `notify@davdeploy.tech`; replies route to
   `support@davdeploy.tech`. Before each beta cohort, run one controlled invitation delivery and
   acceptance check with the intended inbox.
3. Run and record a controlled browser journey on `https://davdeploy.tech`: invitation, account
   creation/sign-in, workspace resolution, plan creation, approval, and sign-out.
4. The customer's GitHub App installation is explicitly approved and limited to its selected
   repositories. The App currently supports read-only analysis; it does not merge or deploy code.
5. The customer has reviewed the AWS connection CloudFormation template and understands that
   discovery is read-only by default. An explicitly acknowledged administrator-pilot setup can
   create a separate execution role, but product execution remains gated and is not a general
   customer deployment promise.

## Operator-led beta workflow

1. Create the customer organisation and its first workspace administrator through the supported
   operator path.
2. Send a time-limited workspace invitation through the active Resend sender and record the
   delivery/acceptance result.
3. Confirm the user can sign in at the canonical domain `https://davdeploy.tech`. The
   `davdeploy-frontend.pages.dev` hostname is not an authenticated application origin.
4. Guide the customer through GitHub App installation/repository selection and AWS discovery-role
   setup. Record consent and the selected account, region, and repository.
5. Generate one plan, identify fixture versus observed evidence, and obtain an independent
   approval. An approved plan is not a deployment.
6. Export the plan/audit evidence and support the customer through the next reviewed action.

## Explicitly unavailable in beta

- Customer workload Terraform apply or destroy through the product.
- Live AWS resource/output ingestion into the customer plan timeline.
- Self-service GitHub App installation initiation, public webhook delivery, or unreviewed PR writes.
- Live AWS pricing as a replacement for customer-approved pricing evidence.
- Enterprise SSO, subscription billing, and automated remediation.

## Operational checks

- Monitor the API, database, worker, DLQ, and migration function alarms.
- Keep CORS limited to `https://davdeploy.tech`.
- Keep customer cloud credentials and GitHub App credentials server-side and short-lived.
- Do not treat fixture planning, local dry runs, or plan-only Terraform review as deployment proof.

See [operations readiness](OPERATIONS_READINESS.md) for the current DLQ assessment and the
incident, recovery, and support handoff procedures.

## Invitation-delivery cost boundary

The `davdeploy.tech` Cloudflare zone is on the Free plan. Cloudflare Email Routing forwards inbound
operational aliases but does not send transactional email. Resend provides the active sender for
workspace invitations; the verified domain sends from `notify@davdeploy.tech` and uses
`support@davdeploy.tech` as Reply-To. The sending key is held in a Standard AWS SSM SecureString,
which is free at the configured tier and is not stored in Terraform state. Resend plan limits still
apply, so delivery volume and provider limits must be reviewed before any broad launch.
