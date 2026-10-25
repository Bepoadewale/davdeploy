# ticket169 — Reconcile public hosted control-plane status

PR: [#169](https://github.com/Bepoadewale/davdeploy/pull/169)
Branch: `docs/hosted-control-plane-status`

## Problem / goal

Correct the public README, which still described the serverless control-plane contract as unapplied
despite the applied API Gateway, Lambda, Aurora, Cognito and SQS control plane.

## Current repo state

The public README contradicted the current deployed runtime and `PROJECT_STATUS.md`. It also mixed
the historical App Runner discovery pilot with the live serverless control plane.

## Research / references used

- Successful protected Terraform plan and apply for commit `6ccb2e5a`.
- Live AWS inventory for the `davdeploy` Aurora cluster, Lambda functions, API Gateway, Cognito,
  SQS queues and alarms.
- Existing customer beta boundary documentation.

## Work planned for the PR

- State the live serverless control plane accurately.
- Preserve boundaries for disabled invitations and customer-workload execution.
- Remove the obsolete “apply the serverless control plane” roadmap statement.

## Acceptance criteria

- [x] README describes the applied hosted components accurately.
- [x] README does not claim customer workload deployment or email invitation delivery.
- [x] Roadmap lists only work that remains.

## Acceptance status

All acceptance criteria are met.

## Tests / validation performed

Documentation-only change. Checked against the protected Terraform apply record and AWS inventory;
no runtime behavior is changed.

## Evidence files produced

No `docs/test/test169.md` file is required because this PR changes documentation only and does not
perform a customer workload test run.

## Boundaries

This PR changes no AWS, GitHub, Cloudflare, identity, email or customer-workload configuration.

## Follow-up work

Keep public status statements synchronized with each material deployment and its recorded evidence.
