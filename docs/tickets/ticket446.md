# ticket446 — isolated SQS retry and dead-letter lifecycle evidence

PR: https://github.com/Bepoadewale/davdeploy/pull/446
Branch: `test/sqs-redrive-lifecycle-446`

## Problem / goal

Record a real, disposable same-account SQS lifecycle run that exercises message
delivery, repeated receives, automatic dead-letter queue transition, and
independent cleanup. This complements the source-only plan policy in PR #445
and the earlier EventBridge-to-SQS delivery test in `test257.md`.

## Current repo state

- Backend `main` is `c874b0de523f26c46561272a05b290ecf782aecc` (PR #445).
- PR #445 adds source-only plan checks for paired SQS retry/DLQ settings and
  direct same-plan Lambda consumers; it does not establish AWS delivery or
  retry behavior.
- Existing `davdeploy-worker` queues are production-tagged and excluded from
  this test.
- The control plane, Terraform state/locks, and Nova execution gates are not
  part of this customer-side test.

## Research / references used

- [`test257.md`](../test/test257.md) — isolated EventBridge-to-SQS message
  delivery, without a consumer or observed DLQ transition.
- [`test445.md`](../test/test445.md) — local generated-plan SQS policy
  regressions.
- AWS [SQS dead-letter queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
  — redrive behavior, same-account/region constraints, and DLQ retention.
- AWS [SQS queue attributes](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_SetQueueAttributes.html)
  — redrive and redrive-allow policies.

## Work planned for the PR

- AWS account `654654474502`, region `us-east-1`; verify identity immediately
  before any mutation.
- Use a unique test prefix `davdeploy-nova-sqs-446-<run-id>` for both queues
  and all test resources. Keep Terraform state local and separate from the
  hosted control plane and production state.
- Inventory found existing `davdeploy-worker` and `davdeploy-worker-dlq`
  queues tagged `Environment=production`. Do not read messages, change, or
  delete either queue.
- Do not modify the hosted control plane, its state, lock, runtime, Nova
  execution gates, or customer credentials.
- Start every Terraform mutation with the repository PID-based run monitor.
  Record run ID, root, PID, and log path. Never overlap mutations on this root.
- Destroy only the newly created test stack after observing delivery and
  redrive. Confirm the exact test queue URLs are absent afterward.
- Keep secrets and credential material out of output and evidence.

### Planned procedure

1. Open this draft PR before creating AWS resources.
2. Create a dedicated SQS standard source queue and DLQ with managed encryption,
   a one-to-one redrive policy at five receives, a `byQueue` allow policy,
   bounded retention/visibility, and run-specific tags.
3. Send one synthetic message. Receive it repeatedly with immediate
   visibility expiration until SQS moves it to the DLQ. Record message IDs and
   approximate receive count without logging message contents or credentials.
4. Receive the message from the DLQ, then run a separate monitored Terraform
   destroy for only this test root. Verify both exact queue URLs are absent.
5. Add `docs/test/test446.md` with exact commands, monitor IDs, timestamps,
   observations, teardown, and remaining limits. No source deployment claim.

## Acceptance criteria

- [x] Draft PR and ticket exist before the first AWS mutation.
- [ ] Caller identity is the expected account and test resources have the
      unique run prefix and test-only tags.
- [ ] Source queue delivers the synthetic message; its receive count advances;
      SQS moves it to the paired DLQ at the configured threshold.
- [ ] DLQ message is readable and identified by its message ID only.
- [ ] Monitored Terraform destroy succeeds for the test root; independently
      verify only the named test queues/resources are absent afterward.
- [ ] Production queues and the hosted control plane are unchanged.
- [ ] Evidence conventions, focused checks, and all seven PR CI checks pass.
- [ ] Documentation states this is same-account service evidence, not Nova
      dispatch, cross-account isolation, application health, or general
      workload certification.

## Acceptance status

Draft PR #446 is open. AWS identity was verified; queue inventory showed two
production-tagged queues, which are excluded. The Terraform monitor has no
active runs. No AWS mutation has been performed. Test evidence is pending.

## Tests / validation performed

- Bootstrap: AWS caller identity verified for account `654654474502`.
- Read-only queue inventory identified the production-tagged queues; no queue
  message was read and no queue setting was changed.
- Terraform monitor: 16 terminal records, zero active.
- No test resources have been created.

## Evidence files produced

- `docs/tickets/ticket446.md`
- `docs/test/test446.md` — to be produced after the run, before review-ready.

## Boundaries

Do not touch the production-tagged queues, the hosted control plane, its state
or locks, Nova execution gates, or customer credentials. Do not claim Nova
dispatch, cross-account isolation, application health, or customer workload
certification from direct SQS operations. Keep output free of credentials and
message contents.

## Follow-up work

Use the observed run to decide whether PR #445's plan shape matches real SQS
redrive behavior. Separately plan producer authorization, Lambda processing,
idempotency, hosted dispatch, pricing, and broader service coverage.
