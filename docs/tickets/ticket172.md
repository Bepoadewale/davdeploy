# ticket172 — Reconcile hosted invitation-delivery documentation

PR: [#172](https://github.com/Bepoadewale/davdeploy/pull/172)
Branch: `docs/operational-email-status`

## Problem / goal

Public operational documents still described invitation delivery as disabled or SES-only after the
verified Resend sender was deployed.

## Current repo state

The hosted API uses Resend for workspace invitations. Its sending-only key is a Standard SSM
SecureString readable only by the API role; Cloudflare Email Routing separately forwards inbound
operational aliases.

## Research / references used

- Merged production configuration from PR #171.
- Successful protected Terraform plan and apply for the serverless control plane.
- Controlled Resend delivery and Cloudflare forwarding checks.

## Work planned for the PR

- Reconcile README, beta, deployment, configuration, operations, and implementation-status text.
- Preserve the remaining browser invitation-acceptance limitation.

## Acceptance criteria

- [x] No public document says the active invitation sender is disabled or SES-only.
- [x] The secret boundary and Cloudflare/Resend responsibilities are accurately described.
- [x] The unrecorded browser acceptance journey remains an explicit follow-up.

## Acceptance status

Documentation reconciliation is complete pending review.

## Tests / validation performed

See `docs/test/test172.md`.

## Evidence files produced

- `docs/test/test172.md`

## Boundaries

This PR changes documentation only. It does not send email, change Cloudflare, alter the SSM
parameter, or deploy infrastructure.

## Follow-up work

Run and record one controlled browser invitation-to-workspace acceptance journey.
