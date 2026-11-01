# ticket215

PR: [#215](https://github.com/Bepoadewale/davdeploy/pull/215)

Branch: `docs/hosted-security-current-state`

## Problem / goal

Reconcile current product documentation with the deployed password-and-
authenticator sign-in, CloudTrail audit trail, and Cloudflare API-edge guard.

## Current repo state

The hosted control plane has Cognito password as its sole first factor,
required software-token MFA, a one-day refresh-token policy, active CloudTrail
management-event logging, and `api.davdeploy.tech` as the protected public API
edge. Several current-state documents still described passwordless email OTP.

## Research / references used

- Live AWS Cognito user-pool and MFA configuration.
- Live CloudTrail status and encrypted audit-bucket configuration.
- Live Worker edge health check and direct API Gateway 403 response.
- Deployed Cloudflare Pages configuration.

## Work planned for the PR

- Update product, implementation, deployment, email, and current-state docs.
- Preserve the customer-workload execution boundary.

## Acceptance criteria

- [x] Current documentation describes password plus authenticator access.
- [x] Current documentation describes the protected API edge and management audit trail.
- [x] Current documentation preserves the planning-only customer deployment boundary.
- [ ] Documentation conventions and required CI pass.

## Acceptance status

Documentation changes are complete locally. Repository validation remains
pending.

## Tests / validation performed

This is documentation-only. No runtime behavior or customer workload was
changed. `git diff --check` passed before the initial commit; CI runs the
documentation convention gate.

## Evidence files produced

No new workload evidence file is required because this PR creates no workload
or infrastructure resource.

## Boundaries

No Terraform, Lambda, Cognito, Cloudflare, database, role, customer record, or
credential changes are made in this PR.

## Follow-up work

Record the controlled live invitation, password-and-authenticator sign-in,
workspace, plan, approval, and sign-out journey.
