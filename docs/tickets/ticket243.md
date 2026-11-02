# ticket243 — Platform module batch reopen

PR: [#243](https://github.com/Bepoadewale/davdeploy/pull/243)

Branch: `feat/module-batch-06-platform`

## Problem / goal

Merge the platform module batch after GitHub closed dependent draft #238.

## Current repo state

AI batch #242 is merged. This PR supersedes closed #238.

## Research / references used

AWS Terraform provider schemas and existing DavDeploy network-module patterns.

## Work planned for the PR

Merge EKS/VPC integration, EC2 autoscaling, VPN and multi-region DNS roots,
plus the registry-root contract test.

## Acceptance criteria

- [x] All 30 registry entries are unique, disabled and point to a module root.
- [x] Platform roots exist and no platform deployment is represented as live.

## Acceptance status

Ready for CI.

## Tests / validation performed

`tests/test_module_implementations.py` passed locally; see `docs/test/test243.md`.

## Evidence files produced

`docs/test/test243.md`

## Boundaries

EKS, NAT, VPN and multi-region DNS remain disabled pending controlled network,
cost, recovery and endpoint-specific lifecycle validation.

## Follow-up work

Run isolated production-like validation only after explicit service scope.
