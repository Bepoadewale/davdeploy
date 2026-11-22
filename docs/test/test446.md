# test446 — isolated SQS retry and dead-letter lifecycle

Date: 2026-11-22

Execution type: Controlled disposable AWS workload validation.

Repository: `Bepoadewale/davdeploy`

Customer repository: None; direct same-account AWS service test.

Commit: `32eaf0b` (SQS module ordering fix; later evidence updates follow)

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The test source queue and tagged DLQ were created with local Terraform state.
The first apply created only the DLQ and failed on source creation; the
source-only retry succeeded after adding an explicit source-to-DLQ dependency
to the module. Both queues were destroyed and independently confirmed absent.
Existing production-tagged queues are excluded.

## Commands executed

- `AWS_PROFILE=ai-platform-pilot-key aws sts get-caller-identity` — verified
  account `654654474502` immediately before apply.
- `terraform -chdir=/tmp/davdeploy-nova-sqs-446-nov22a1 init -backend=false` —
  initialized AWS provider 5.100.0.
- `terraform -chdir=/tmp/davdeploy-nova-sqs-446-nov22a1 validate` — passed.
- Initial `terraform plan` — reviewed: two creates, zero changes, zero
  destroys.
- First monitored apply `nova-sqs-446-create-nov22a1` failed with exit 1 after
  creating only the DLQ. SQS rejected source creation because the DLQ target
  did not exist when the source was submitted. It started at
  `2026-11-22T21:37:11Z` (supervisor PID 63460, Terraform PID 63461), root
  `/private/tmp/davdeploy-nova-sqs-446-nov22a1`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-446-create-nov22a1.log`.
- Added `depends_on = [aws_sqs_queue.dlq]` to the SQS module's source queue.
  `terraform validate` passed; `terraform graph` confirmed the source-to-DLQ
  dependency. The retry plan includes only the source queue create.
- Retry plan `create-source.tfplan` — one source queue create, zero changes,
  zero destroys.
- Monitored retry `nova-sqs-446-source-nov22a1` succeeded: one resource added,
  zero changed, zero destroyed. It started at `2026-11-22T21:43:11Z`
  (supervisor PID 65529, Terraform PID 65530), root
  `/private/tmp/davdeploy-nova-sqs-446-nov22a1`. Log:
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-446-source-nov22a1.log`.
- `aws sqs send-message` returned message ID
  `442f76aa-5ddb-4341-ab8c-2793c205897e`; message body was not logged.
- Six source receive attempts returned the same message ID with approximate
  receive counts 1–5, then no source message after the count exceeded five.
- A DLQ receive returned that same message ID with receive count 6. No message
  was deleted or redriven manually.
- Reviewed saved destroy plan: exactly the source and DLQ queues are deleted;
  zero resources are created or updated.
- Saved-plan teardown `nova-sqs-446-destroy-nov22a1` started at
  `2026-11-22T21:50:42Z` (supervisor PID 68532, Terraform PID 68533), root
  `/private/tmp/davdeploy-nova-sqs-446-nov22a1`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-sqs-446-destroy-nov22a1.log`.
  It succeeded with zero added, zero changed, two destroyed.
- Independent inventory returned no URLs under the test prefix, local
  Terraform state is empty, and existing `davdeploy-worker` remains tagged
  `Environment=production`.
- Final Terraform monitor: 19 terminal records, zero active runs.
- GitHub Actions run [45074340234](https://github.com/Bepoadewale/davdeploy/actions/runs/45074340234)
  passed all seven checks on PR #446 head `bd18e2052845ee2a207d60a3a021888b13596c65`.
  That head contains the SQS module fix; later evidence and goal-status
  documentation updates followed.
- GitHub Actions run [45075255587](https://github.com/Bepoadewale/davdeploy/actions/runs/45075255587)
  passed all seven checks on PR #446 head `c3f4d76425a0a4abe94c1cf285fc0c024f35a694`.
  This run includes the lifecycle evidence and Nova status-documentation update.

## Observed result

The source-to-DLQ receive and automatic redrive passed. Monitored teardown
destroyed only the test queues, and independent checks confirmed both are
absent.

## Teardown

The monitored saved-plan teardown destroyed only the test source and DLQ.
Independent inventory confirmed both queue URLs are absent.

## Final boundary

This direct same-account SQS test does not establish Nova dispatch,
cross-account isolation, Lambda consumer execution, application health,
idempotency, or general customer workload certification. The hosted control
plane, its Terraform state/locks, production queues, and Nova execution gates
were not changed.
