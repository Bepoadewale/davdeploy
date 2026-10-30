# ticket205 - Declare sensitive API routes for throttling

PR: [#205](https://github.com/Bepoadewale/davdeploy/pull/205)
Branch: `fix/declare-sensitive-api-routes`

## Problem / goal

Make the route-level rate limits introduced in PR #203 enforceable by declaring the corresponding
HTTP API routes explicitly.

## Current repo state

The API uses a JWT-protected `$default` route. The first corrected security apply created the API
access-log group and metric filters, but API Gateway rejected stage route settings because no
matching explicit route existed. The failed apply made no destructive change.

## Research / references used

The failed Terraform apply run 40988047541, API Gateway HTTP API route-selection behavior, and the
existing `$default` route, JWT authorizer, and Lambda proxy integration.

## Work planned for the PR

Declare the eight sensitive route keys with the same JWT authorizer and Lambda integration as the
existing `$default` route. Generate stage rate settings from the same route-limit map so a limit
cannot exist without a matching route.

## Acceptance criteria

- [x] Every limited route is explicitly declared in API Gateway.
- [x] Every explicit route uses the existing JWT authorizer and Lambda proxy integration.
- [x] Stage route settings are generated from the same map as the routes.
- [x] `$default` remains the authenticated fallback for all other product API routes.

## Acceptance status

Implemented locally; pending CI, plan review, and a retry of the protected Terraform apply.

## Tests / validation performed

Recorded in `docs/test/test205.md`.

## Evidence files produced

`docs/test/test205.md`.

## Boundaries

This PR declares routes and applies existing limits only. It does not alter request handlers,
authentication policy, browser behavior, customer cloud access, or workload execution.

## Follow-up work

After apply, verify the stage reports all eight route settings and test one safe throttled request
against a non-customer, authenticated fixture path if a controlled test identity is available.
