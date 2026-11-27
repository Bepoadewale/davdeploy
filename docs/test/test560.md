# test560 — Lambda health-target feedback

Date: 2026-11-27

Execution type: Hosted plan-only diagnostic baseline; no customer AWS workload

Customer repository: Synthetic DavDeploy acceptance case

Commit: `fe02d62f123e27712fee686db05029de8b7a33af` (deployed baseline)

AWS account: `654654474502` (control-plane release only)

AWS region: `us-east-1`

## Hosted v21 baseline

- Authenticated, read-only `GET /api/v1/generated-plan-runs/d61e0c32-0379-4bd2-a240-a7924f4e98a1`
  returned `FAILED`, prompt `terraform-nova2-contract-v21`, two generation
  attempts, one repair, and no artifact.
- Sanitized feedback identifies `incompatible_health_target` at
  `health_assertions[*].target_resource_id`, with assertion kind
  `container_readiness` and observed resource type `aws_lambda_function`.
- The fixed guidance lists allowed targets but does not explain how to preserve
  an HTTP or asynchronous health requirement when the application runtime is a
  Lambda function. No raw proposal, plan, state, or credential was retrieved.
- The repository Terraform run monitor has 75 historical records and no active
  mutation. AWS identity was verified as account `654654474502`.

## Resources and execution boundary

No customer workload AWS resources were created or changed. The run failed
before a CodeBuild artifact or Terraform plan. No customer approval, apply, or
destroy occurred. This does not establish application health, pricing, plan
policy, or lifecycle behavior.

## Implementation verification

Pending implementation, focused tests, full verification, clean-room proof,
PR review/CI, protected control-plane deployment, and a fresh review-only
hosted generation attempt.
