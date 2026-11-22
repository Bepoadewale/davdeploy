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
- Its SQS module derives both queue ARNs, so Terraform did not infer that the
  source queue must wait for the DLQ. The first disposable apply exposed this
  creation-order race; this PR adds an explicit dependency.
- Existing `davdeploy-worker` and `davdeploy-worker-dlq` queues are tagged
  `Environment=production` and excluded from this test.
- The hosted control plane, its Terraform state/locks, and Nova execution gates
  are outside this customer-side test.

## Research / references used

- [`test257.md`](../test/test257.md) — EventBridge-to-SQS delivery, without a
  consumer or observed DLQ transition.
- [`test445.md`](../test/test445.md) — local generated-plan SQS policy checks.
- AWS [SQS dead-letter queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
  — redrive behavior, same-account/region constraints, and DLQ retention.
- AWS [SQS queue attributes](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_SetQueueAttributes.html)
  — redrive and redrive-allow policies; messages move after their receive count
  exceeds `maxReceiveCount`.

## Work planned for the PR

1. Open this draft PR before any AWS mutation.
2. Make the source queue explicitly depend on the DLQ in the SQS Terraform
   module so the redrive target exists before SQS creates the source.
3. Create a dedicated SQS standard source queue and DLQ with managed
   encryption, one-to-one redrive at five receives, a `byQueue` allow policy,
   bounded retention/visibility, and test-only tags.
4. Send one synthetic message. Receive it repeatedly with immediate visibility
   expiration until SQS moves it to the DLQ. Record only message IDs and
   approximate receive counts, not message contents or credentials.
5. Receive the message from the DLQ. Run a separate monitored Terraform
   destroy for only this test root and independently verify both exact test
   queue URLs are absent.
6. Add `docs/test/test446.md` with commands, monitor IDs, observations,
   teardown, and limitations. Do not claim source deployment.

## Acceptance criteria

- [x] Draft PR and ticket exist before the first AWS mutation.
- [ ] Caller identity is the expected account; resources use the unique
      `davdeploy-nova-sqs-446-nov22a1` prefix and test-only tags.
- [ ] The source queue delivers the synthetic message and its receive count
      advances; SQS moves it to the paired DLQ after the count exceeds the
      configured `maxReceiveCount` of 5.
- [ ] Terraform graph and monitored apply confirm the source queue depends on
      successful DLQ creation.
- [ ] The DLQ message is readable and identified by its message ID only.
- [ ] Monitored Terraform destroy succeeds for the test root; independently
      verify the named test queues/resources are absent afterward.
- [ ] Production queues and the hosted control plane remain unchanged.
- [ ] Evidence conventions, focused checks, and all seven PR CI checks pass.
- [ ] Documentation says this is same-account service evidence, not Nova
      dispatch, cross-account isolation, application health, or general
      workload certification.

## Acceptance status

Draft PR #446 is open. AWS identity was verified as account `654654474502`.
Read-only inventory found two production-tagged queues; neither was read or
changed. Initial run `nova-sqs-446-create-nov22a1` failed with exit 1 after
creating only the test DLQ; SQS rejected source creation because Terraform had
no creation dependency. The source-only retry
`nova-sqs-446-source-nov22a1` started at `2026-11-22T21:43:11Z` after adding
the dependency; its terminal result is pending. No message test has started.

## Tests / validation performed

- `AWS_PROFILE=ai-platform-pilot-key aws sts get-caller-identity` — expected
  account `654654474502`.
- `aws sqs list-queue-tags` — the existing production queue pair is tagged
  `Environment=production`; no messages were read.
- Terraform monitor before mutation: 16 terminal records, zero active.
- Checked the unique source queue did not exist before planning.
- Local Terraform root initialized AWS provider 5.100.0 and passed
  `terraform validate`.
- Reviewed saved plan: exactly two queue creates, zero changes, zero destroys.
- First monitored apply `nova-sqs-446-create-nov22a1` (supervisor PID 63460,
  Terraform PID 63461, root `/private/tmp/davdeploy-nova-sqs-446-nov22a1`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-446-create-nov22a1.log`)
  failed with exit 1. It created only the tagged test DLQ; the source queue was
  confirmed absent. No production queue was affected.
- Added `depends_on = [aws_sqs_queue.dlq]` to the source queue in
  `modules/sqs-queue`. Module validation passed, and Terraform graph output
  contains `module.queue.aws_sqs_queue.this -> module.queue.aws_sqs_queue.dlq`.
- Retry plan contains only one source queue create, zero changes, and zero
  destroys. Its monitored apply is in progress; the message test has not run.
- Documentation convention and diff checks passed on the bootstrap ticket.

## Evidence files produced

- `docs/tickets/ticket446.md`
- `docs/test/test446.md` — to be completed before review-ready status.

## Boundaries

Use only the test prefix `davdeploy-nova-sqs-446-nov22a1` in account
`654654474502`, region `us-east-1`. Keep Terraform state local and isolated
from production and the hosted control plane. Start each Terraform mutation
through the PID monitor and record its run ID, root, PID, and log path. Never
overlap mutations on the root. Destroy only this test stack after observing
delivery and redrive. Do not touch the production-tagged queues, control-plane
state/locks/runtime, Nova execution gates, or customer credentials. Keep
message contents, credentials, and secrets out of output and evidence.

Do not claim Nova dispatch, cross-account isolation, application health, or
customer workload certification from direct SQS operations.

## Follow-up work

Use the observed run to verify PR #445's plan shape against actual SQS redrive
behavior. Separately address producer authorization, Lambda processing,
idempotency, hosted dispatch, pricing, and broader service coverage.
