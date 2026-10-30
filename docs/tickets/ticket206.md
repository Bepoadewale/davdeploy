# ticket206

PR: Pending

Branch: `fix/order-sensitive-api-route-limits`

## Problem / goal

Ensure API Gateway creates all sensitive, explicitly throttled routes before it
updates the default stage with settings that reference those routes.

## Current repo state

PR #205 added explicit authenticated routes and their per-route throttling
settings. Its first production apply created the routes but API Gateway rejected
the concurrent stage update because one route was not yet visible to the stage
operation.

## Research / references used

The failed Terraform apply for run `40989344427` reported `UpdateStage` could
not find `DELETE /api/v1/api-credentials/{credential_id}`. The same run shows
that route was created successfully immediately before the failed stage update.

## Work planned for the PR

- Make the API Gateway default stage depend on the sensitive-route resource.
- Cover that ordering constraint with the existing Terraform source test.

## Acceptance criteria

- A Terraform apply creates or reconciles sensitive routes before updating their
  stage route settings.
- The stage can apply the route limits without a route-not-found error.

## Acceptance status

In progress.

## Tests / validation performed

Pending local validation and CI.

## Evidence files produced

- `docs/test/test206.md`

## Boundaries

This only orders existing API Gateway resources. It does not change API routes,
authorization, throttling values, customer data, or execution permissions.

## Follow-up work

After the deployment completes, verify the deployed stage settings, routes,
metric filters, alarms, and Lambda rate-limit environment value with read-only
AWS queries.
