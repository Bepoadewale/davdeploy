# Provider activation plan

No provider account or credential is required for the local demo. The defaults
in `.env.example` intentionally keep all external adapters disabled.

## Recommended low-cost path

1. **Google Workspace OIDC — internal team first.** Create a Google OAuth
   client only after a production hostname exists. Persist the Google `sub`
   identifier; use the Workspace `hd` claim to restrict internal access. Do
   not use an email address as the primary identity key.
2. **Amazon Cognito — customer sign-in later.** Create a User Pool in the
   chosen control-plane region, then set its issuer, JWKS URL and app-client
   audience through the generic OIDC variables. davdeploy will still map
   verified subjects to server-side workspace membership.
3. **Resend — active transactional invitations.** The verified `davdeploy.tech` domain sends
   workspace invitations through a runtime-only SSM key. Cloudflare Email Routing receives and
   forwards operational aliases separately. Follow [email operations](EMAIL_OPERATIONS.md) for
   alias, rotation, and provider-change controls.
4. **Manual beta entitlements — no cards.** Keep `DAVDEPLOY_BILLING_PROVIDER=manual`
   until paid plans exist. Stripe is the intended later webhook source; its
   events must update the local entitlement records, never bypass them.
5. **Local analytics first.** Activate PostHog only after its data region,
   retention and customer-consent settings are approved.

## Activation safeguards

- Secrets live in the deployed secret manager, never `.env.example`, the
  browser, the database, or Git.
- Configure the external provider webhook as at-least-once and deduplicate its
  event ID before changing state.
- Run `make validate-environment` before enabling hosted mode.
- Enabling a provider is a separate reviewed change; this repository makes no
  provider calls merely from configuration values.
