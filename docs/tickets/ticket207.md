# ticket207

PR: Pending

Branch: `fix/allow-api-gateway-log-delivery`

## Problem / goal

Permit the Terraform apply role to create the CloudWatch Logs delivery required
when API Gateway enables the DavDeploy API stage access logs.

## Current repo state

The retry after PR #206 created the API Gateway routes and started the stage
update successfully, but production apply `40990740167` stopped at
`logs:CreateLogDelivery`. The API Gateway access log group and metric filters
already exist; the missing permission is limited to the delivery control plane.

## Research / references used

The failed apply error explicitly identifies `logs:CreateLogDelivery`. AWS
CloudWatch Logs does not offer resource-level permissions for log-delivery
management, so the limited set of lifecycle actions requires `Resource: "*"`.

## Work planned for the PR

- Add only the five CloudWatch Logs log-delivery lifecycle actions needed for
  API Gateway stage access logging.
- Add a source contract test for the dedicated policy statement.

## Acceptance criteria

- The apply role can create, inspect, update, delete, and list log deliveries.
- No unrelated CloudWatch Logs write action is broadened.
- Bootstrap Terraform and source tests pass.

## Acceptance status

In progress.

## Tests / validation performed

Pending local validation and CI.

## Evidence files produced

- `docs/test/test207.md`

## Boundaries

This changes only the Terraform apply role's permissions to manage the access
log delivery API. It does not create a customer workload or alter customer
data, authentication, execution permissions, or rate-limit values.

## Follow-up work

Apply this bootstrap policy and retry the reviewed serverless-control-plane
plan. Then verify the deployed API stage settings and security alarms read-only.
