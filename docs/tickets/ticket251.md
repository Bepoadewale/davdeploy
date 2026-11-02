# ticket251 — Real web workload certification

PR: [#251](https://github.com/Bepoadewale/davdeploy/pull/251)

Branch: `test/real-web-workload`

## Problem / goal

Prove a disposable customer-style API workload serves real traffic and cleans up.

## Current repo state

Resource lifecycle validation exists but application response evidence was absent.

## Research / references used

Existing delivery module and universal certification evidence rules.

## Work planned for the PR

Run an API Gateway/Lambda workload, record health response and teardown.

## Acceptance criteria

- [x] API returns HTTP 200.
- [x] All owned test resources are destroyed.

## Acceptance status

Complete.

## Tests / validation performed

Recorded in `docs/test/test250.md`.

## Evidence files produced

`docs/test/test250.md`

## Boundaries

This validates the API workload only, not CloudFront, identity or DNS/TLS.

## Follow-up work

Run composed static-web and identity/DNS workload certification.
