# ticket330 — design tenant-isolated Terraform state

PR: [#330](https://github.com/Bepoadewale/davdeploy/pull/330) (draft)
Branch: `docs/nova-state-backend-adr-330`
Base: `main` after PR #328 merged as `64bfd2c55cf22b61c20305106dcbcec65ef48352`

## Current repo state

PR #328's Nova runner is merged in source but disabled, backend-free, not deployed, and unable to produce an approvable plan. Direct shared CodeBuild access to all tenant state is not allowed. The pricing implementation from closed PR #318 remains held for account-owner direction.

## Problem / goal

Choose a Terraform state boundary that allows durable plan/apply/update/recovery/teardown while preserving tenant/workspace/project isolation, sensitive-state handling, locking, state history, and reconciliation. Keep Terraform and the existing CodeBuild/API architecture; do not introduce a second IaC engine or purchase an external state service.

## Work planned for the PR

- Record a proposed architecture decision for an HTTP-backend state API backed by versioned encrypted S3 objects and PostgreSQL locks.
- Define the trusted state ID, short-lived run-bound credential, lock/recovery contract, state-version plan binding, and teardown retention.
- Compare direct S3 roles and external state services; preserve the direct-S3 `use_lockfile`/versioning alternative if constraints change.
- Make clear that this design is not implementation, deployment, or permission to enable customer apply.

## Acceptance criteria

- [x] The proposed backend does not grant shared CodeBuild or customer roles direct state-bucket access.
- [x] State identity, access token scope, lock, version history, recovery, plan/apply freshness, and teardown retention requirements are explicit.
- [x] Terraform backend behavior and S3 locking/versioning alternatives reference current official documentation.
- [x] The decision records alternatives and measured implementation gates without claiming state functionality exists.

## Evidence

- Official HashiCorp docs reviewed 2026-11-10: HTTP backend, S3 backend, state locking, and sensitive state.
- PR #328 is source-only and un-deployed; no state infrastructure or customer workload was created.

## Acceptance status

ADR-013 is proposed for review. It selects a DavDeploy HTTP state API backed by S3 versions and PostgreSQL lock rows, subject to size, availability, and failure-recovery tests before enabling.

## Tests / validation performed

- Documentation convention check and `git diff --check` are required before push.
- No runtime code, AWS calls, or resource mutations are part of this PR.

## Scope boundary

This PR defines a design only. It does not create a bucket, roles, tokens, API routes, locks, Terraform backend configuration, customer plans, or apply/destroy capability.

## Evidence files produced

- `docs/decisions/ADR-013-tenant-isolated-terraform-state.md`
- `docs/tickets/ticket330.md`

## Research / references used

- [Terraform HTTP backend](https://developer.hashicorp.com/terraform/language/backend/http)
- [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3)
- [Terraform state locking](https://developer.hashicorp.com/terraform/language/state/locking)
- [Terraform sensitive state](https://developer.hashicorp.com/terraform/language/manage-sensitive-data)

## Boundaries

No code implementation or deployment is claimed. The current Nova runner stays disabled and unapprovable.

## Follow-up work

If ADR-013 is accepted, implement and test the state API, versioned S3 storage, Postgres locking, token lifecycle, state-bound saved plans, and crash recovery in a separate executable PR before attempting customer apply.
