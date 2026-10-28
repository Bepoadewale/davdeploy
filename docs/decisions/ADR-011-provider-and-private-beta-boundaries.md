# ADR-011: Provider and private-beta boundaries

## Status

Accepted. The Resend/Cloudflare email portion was activated through reviewed configuration; legal
and broader private-beta gates remain separate.

## Context

davdeploy will initially use Google Workspace and AWS. The product needs a
low-cost private-beta path that preserves its tenant and audit boundaries while
avoiding premature provider lock-in or customer-facing commercial claims.

## Decisions

### 1. Production domain layout

Reserve these names under the eventual primary product domain:

- `app.<domain>` for the browser product;
- `api.<domain>` for the governed API; and
- `status.<domain>` for public operational communication.

OAuth redirect URIs, cookie/security policy, email sender alignment and public
documentation must use these stable names. No domain is registered or changed
by this decision.

### 2. Identity split

Use Google Workspace OIDC for davdeploy's internal operators and Amazon
Cognito User Pools for customer-facing identities. Both are mapped to the
server-side `ProductUser` and workspace membership records; an identity-token
organization, role, or email claim never grants access by itself.

Google identity uses the immutable `sub` as the identity key. Workspace
restriction checks the `hd` claim rather than inferring membership from an
email address. Cognito is configured through the existing generic OIDC/JWKS
contract before it is activated.

### 3. First hosted region and residency

Use `us-east-1` as the default first control-plane region. Customer-specific
data residency requirements are a sales/contract review gate, not an implicit
fallback. The tenant/cell/region fields remain the source of truth for a later
regional deployment.

### 4. Transactional email progression

Use Resend for transactional invitations and Cognito account/authentication email from the verified
product domain, with Cloudflare Email Routing for inbound operational aliases. The sending key is
runtime-only Parameter Store material. Cognito invokes a dedicated custom-email sender, so current
code delivery does not depend on Amazon SES production access or recipient verification. SES stays
configured on the user pool as a fallback only.
Email is not used as an authorization channel: invitation acceptance always requires an
authenticated identity and server-side membership validation.

### 5. Commercial policy

Private-beta customers receive manually assigned `ACTIVE` entitlements and
explicit quota limits. No card collection, invoicing, or automatic upgrade path
is enabled during the beta. Stripe Billing is the later payment processor; its
verified webhook events may update davdeploy subscription records but may
not bypass entitlement checks or audit records.

### 6. Privacy, retention, and legal readiness

Before external customer data is accepted, publish lawyer-reviewed Terms of
Service, Privacy Policy, DPA, retention schedule, export/deletion procedure,
and incident contact channel. Template generators may help draft text but are
not a substitute for legal review. Product data-lifecycle requests remain
operator-approved until the retention backend and legal requirements are
implemented and verified.

## Consequences

- Google Workspace and Cognito are deliberately separate trust domains.
- The product can run private beta without payments or bulk-email infrastructure.
- AWS resource provisioning is not authorized by this ADR.
- Provider credentials, account IDs, client IDs, domains, and legal documents
  are deployer-owned configuration, never repository content.

## Activation checklist

1. Register/verify the production domain and set DNS ownership controls.
2. Create the Google OAuth client and allowlisted redirect URI for internal use.
3. Create the Cognito User Pool and app client only when customer sign-in is
   ready; configure issuer, audience, and JWKS settings through secret-managed
   deployment configuration.
4. Keep the sender domain verified, the forwarding destinations explicitly verified, and the
   product sender changes behind a reviewed deployment.
5. Complete legal review before opening public sign-up or uploading customer
   repository/cloud evidence.
6. Run `make validate-environment` and a two-tenant authorization proof before
   any hosted activation.
