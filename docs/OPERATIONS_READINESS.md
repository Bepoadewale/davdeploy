# Operations readiness

This runbook is for the hosted DavDeploy control plane. It distinguishes read-only investigation
from state-changing recovery. It does not authorise customer-cloud deployment, queue replay, or
message deletion.

## Current read-only DLQ assessment

Checked 2026-10-28 in `us-east-1`:

- `davdeploy-worker`: zero visible, in-flight, and delayed messages.
- `davdeploy-worker-dlq`: zero visible and in-flight messages.
- `davdeploy-worker-dead-letter` and `davdeploy-worker-errors` alarms: `OK`.
- The worker is deployed with `DAVDEPLOY_MODEL_PROVIDER=bedrock`; the compatibility fix also
  accepts the historic `bedrock-nova` value without broadening allowed providers.

The historic DLQ cause was worker startup rejecting the legacy provider value. See
[`ticket166`](tickets/ticket166.md). This assessment did not receive, replay, change visibility,
delete, or otherwise mutate an SQS message.

## DLQ incident procedure

1. Read queue counts, alarm state, worker configuration, and bounded CloudWatch logs.
2. Classify the failure by code/configuration, dependency, authorization, malformed input, or
   unknown cause. Record message count, time window, and the safe recovery hypothesis.
3. Correct and deploy the smallest fail-closed fix. Prove the worker initializes before proposing
   recovery.
4. Request a separate incident decision naming the exact messages, replay method, expected
   idempotency behavior, rollback, and customer impact.
5. Only after that decision, replay or remove messages. Record the outcome and return alarms to
   normal.

## Incident response

1. Acknowledge the alarm and establish customer impact from the tenant-scoped audit trail.
2. Preserve evidence: alarm state, relevant request IDs, deployment commit, and redacted logs.
3. Stop at the product boundary: do not use customer credentials, execute Terraform, or mutate a
   customer account while diagnosing the control plane.
4. Publish a plain-English status update through the support route. State what is affected, what
   is not affected, next update time, and any customer action required.
5. After recovery, document cause, timeline, safeguards, and follow-up owner.

## Backup and recovery drill procedure

Aurora backups and deletion protection are enabled, but restore evidence is not yet recorded.
Before a drill, obtain explicit approval because it creates recovery resources and may incur AWS
charges.

1. Define a non-production recovery target, expected recovery point, time objective, and owner.
2. Restore only into an isolated target. Do not replace the live cluster.
3. Run authenticated read-only API smoke checks against the recovered data with synthetic or
   approved test identities.
4. Record recovery duration, integrity checks, cleanup plan, and actual cost.
5. Obtain explicit approval before deleting the isolated recovery target.

## Support handoff

- `support@davdeploy.tech`: customer questions, access issues, and incident contact.
- `notify@davdeploy.tech`: invitations, plan notifications, and security notices; replies route
  to support.
- A support report should include workspace name, approximate time, page/action, safe request ID
  if shown, and a screenshot with tokens, codes, account IDs, and secret values redacted.
- Support must not request AWS access keys, GitHub App private keys, Terraform state, or Cognito
  verification codes.

## Boundaries

This runbook does not enable production execution. Approved plans remain governed decisions until
a separately authorised customer-cloud execution pilot exists.
