# ticket208

PR: Pending

Branch: `fix/allow-api-gateway-log-policy`

## Problem / goal

Complete the documented minimum CloudWatch Logs permissions API Gateway needs
to enable HTTP API access logging for the first time.

## Current repo state

PR #207 deployed the log-delivery lifecycle actions. The next reviewed
serverless apply then reached the API Gateway stage update but stopped with
`BadRequestException: Insufficient permissions to enable logging`. This is the
remaining CloudWatch Logs resource-policy prerequisite.

## Research / references used

AWS HTTP API logging documentation lists `logs:DescribeLogGroups`,
`logs:DescribeResourcePolicies`, and `logs:PutResourcePolicy` alongside the
log-delivery actions. AWS notes these permissions require wildcard resources.

## Work planned for the PR

- Add the three documented access-log resource-policy actions to the existing
  dedicated log-delivery statement.
- Extend the Terraform source contract test.

## Acceptance criteria

- The apply role has the complete documented minimum set for HTTP API access
  logging.
- The additional wildcard permissions are limited to the three required
  CloudWatch Logs control-plane actions.
- Validation and CI pass.

## Acceptance status

In progress.

## Tests / validation performed

Pending local validation and CI.

## Evidence files produced

- `docs/test/test208.md`

## Boundaries

This only permits configuration of the CloudWatch Logs delivery resource
policy required for DavDeploy API access logs. It does not permit application
log reads, workload changes, or customer-data operations.

## Follow-up work

Apply the reviewed bootstrap update, then replan and apply the serverless
control plane and verify the deployed rate-limiting and alerting controls.
