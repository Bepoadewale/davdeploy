# ticket260 — Real public multi-region DNS failover certification

PR: Pending creation.

Branch: `test/real-public-dns-failover`

## Problem / goal

Prove a public, delegated temporary DavDeploy child zone resolves a real
Route 53 primary/secondary failover record to two independently hosted health
endpoints.

## Current repo state

The existing validation zone is an un-delegated `.invalid` domain, so it only
proves Route 53 resource lifecycle.

## Research / references used

Route 53 failover routing and health-check guidance; Cloudflare DNS delegation
API; existing disposable validation modules.

## Work planned for the PR

Create regional S3 website health origins, delegate one temporary child zone
through Cloudflare NS records, prove public DNS resolution and health checks,
then remove AWS resources and the delegation.

## Acceptance criteria

- [ ] Public DNS resolves the delegated temporary name.
- [ ] Route 53 reports both health endpoints healthy.
- [ ] Temporary AWS resources and Cloudflare delegation are removed.

## Acceptance status

In progress.

## Tests / validation performed

Terraform validation passed locally.

## Evidence files produced

`docs/test/test260.md`

## Boundaries

The public website origins exist only for this short certification run.

## Follow-up work

Induce and observe a controlled primary failure before cleanup.
