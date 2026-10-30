# ticket204 - Allow scoped API security log controls

PR: [#204](https://github.com/Bepoadewale/davdeploy/pull/204)
Branch: `fix/allow-api-security-log-controls`

## Problem / goal

Repair the least-privilege Terraform apply policy after the rate-limit deployment failed to create
the scoped API Gateway access-log group. Permit only the operations needed to manage the existing
DavDeploy API security log group and its metric filters.

## Current repo state

PR #203 merged and its saved production plan started applying. It created three API response burst
alarms, two Cognito alarms, and updated Lambda packages, then stopped at
`logs:CreateLogGroup` for `/aws/apigateway/davdeploy`. The existing apply policy permits only
`/aws/lambda/davdeploy-*` log groups and does not permit metric filters.

## Research / references used

The failed Terraform apply run 40975713772, the bootstrap apply-policy source, and the API Gateway
access-log and CloudWatch metric-filter resources introduced by PR #203.

## Work planned for the PR

Extend the existing operational-log statement with the two exact API Gateway log-group ARN forms
and `logs:PutMetricFilter` plus `logs:DeleteMetricFilter`. Add a contract test proving the policy
does not grant broad log-group access.

## Acceptance criteria

- [x] The apply role can create and manage only `/aws/apigateway/davdeploy*` log groups.
- [x] The apply role can create and remove metric filters only in the already scoped log groups.
- [x] No wildcard log-group resource is introduced.
- [x] The bootstrap Terraform root validates and policy scope is tested.

## Acceptance status

Implemented locally; pending CI, reviewed bootstrap-policy deployment, and retry of the saved
control-plane plan.

## Tests / validation performed

Recorded in `docs/test/test204.md`.

## Evidence files produced

`docs/test/test204.md`.

## Boundaries

This PR changes only the Terraform apply role's scoped logging permissions. It does not create,
delete, or alter a customer cloud resource, customer workload, authentication setting, or secret.

## Follow-up work

Apply the bootstrap policy, then rerun the current serverless-control-plane Terraform plan and
apply. Confirm the remaining API stage, access-log, metric-filter, and alarm resources converge.
