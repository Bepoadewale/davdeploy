# ticket170 — Add a Resend invitation delivery adapter

PR: [#170](https://github.com/Bepoadewale/davdeploy/pull/170)
Branch: `feat/resend-invitation-delivery`

## Problem / goal

Allow the hosted control plane to send workspace invitations through Resend after the sender domain
is verified, without enabling Amazon SES.

## Current repo state

Workspace invitations and their delivery lifecycle already exist. Hosted delivery is disabled unless
an SES sender is configured. Cloudflare Email Routing now forwards the DavDeploy operational aliases
to the founder inbox, while Resend sender-domain activation remains separate.

## Research / references used

- Resend Email API and SMTP documentation.
- Existing bounded Amazon SES invitation adapter and invitation lifecycle tests.

## Work planned for the PR

- Add a Resend HTTPS invitation adapter using the existing `httpx` dependency.
- Add explicit sender and reply-to configuration.
- Preserve disabled-by-default hosted behavior until a Resend key and verified sender are supplied.

## Acceptance criteria

- [x] Resend sends one recipient-bound invitation with a safe acceptance link.
- [x] Invitation replies route to the configured support address.
- [x] Provider failures do not expose secrets and are represented as invitation-delivery failures.
- [x] Existing application tests pass.

## Acceptance status

All local code acceptance criteria are met. Live delivery remains intentionally disabled until the
Resend domain and production secret are configured.

## Tests / validation performed

See `docs/test/test170.md`.

## Evidence files produced

- `docs/test/test170.md`

## Boundaries

No live Resend message is sent. This change does not place a Resend secret in source control,
activate an email provider, or modify customer data.

## Follow-up work

Create and verify the Resend sender domain, store a sending-only key in the hosted runtime, deploy,
and run a controlled invitation journey.
