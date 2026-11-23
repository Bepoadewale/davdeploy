# ticket458 — verify AWS Batch failure retry and recovery

PR: https://github.com/Bepoadewale/davdeploy/pull/458
Branch: `test/batch-retry-recovery-458`

## Current repo state

- Backend source baseline is PR #456; the latest docs-only reconciliation is
  PR #457.
- [`test252.md`](../test/test252.md) proves a successful disposable Fargate
  Batch job and teardown, but does not record a failed attempt followed by an
  automatic retry and success.
- AWS account `654654474502`, region `us-east-1`; the hosted control plane and
  its Terraform state/locks are out of scope.

## Problem / goal

Prove one finite AWS Batch Fargate retry path: the first container attempt exits
nonzero, AWS Batch starts one retry, the second attempt exits successfully, and
the disposable stack is removed. Keep Batch job-definition retention and any
cost-free inactive definition status explicit.

## Research / references used

- AWS [automated job retries](https://docs.aws.amazon.com/batch/latest/userguide/job_retries.html)
  documents retrying nonzero container exit codes and the attempt counter.
- AWS [Batch job environment variables](https://docs.aws.amazon.com/batch/latest/userguide/job_env_vars.html)
  defines `AWS_BATCH_JOB_ATTEMPT` as the current attempt number.
- AWS [job definition parameters](https://docs.aws.amazon.com/batch/latest/userguide/job_definition_parameters.html)
  documents the job definition retry strategy and 1–10 attempt range.
- AWS [DeregisterJobDefinition API](https://docs.aws.amazon.com/batch/latest/APIReference/API_DeregisterJobDefinition.html)
  states that deregistered job definitions are permanently deleted after 180 days.
- [`test252.md`](../test/test252.md) — existing direct Batch Fargate execution
  and teardown evidence.

## Work planned for the PR

1. Add a pinned, tagged Terraform fixture with one Fargate compute environment,
   queue, two-attempt job definition, scoped roles, security group, and short-
   retention log group.
2. Make the synthetic container fail only on attempt one by checking
   `AWS_BATCH_JOB_ATTEMPT`; verify exit code 1 followed by exit code 0 and final
   `SUCCEEDED` status.
3. Redact job IDs, log stream names, job output, and AWS error details from the
   probe result.
4. Open the PR and evidence files before AWS writes. Run the workload in account
   `654654474502`, region `us-east-1`, through the Terraform run monitor.
5. Destroy the exact stack through the monitor, independently verify resource
   absence, and record any AWS-managed inactive job-definition retention.

## Evidence used

- AWS documentation linked above.
- Existing success-only evidence in [`test252.md`](../test/test252.md).

## Acceptance criteria

- [x] The saved create plan contains exactly nine creates and no updates/deletes.
- [x] AWS Batch records two attempts: attempt one exits `1`; attempt two exits
      `0`; the final job status is `SUCCEEDED`.
- [x] Attempt markers are verified from the two CloudWatch log streams, while
      probe output omits IDs, stream names, job output, and AWS errors.
- [x] Reviewed exact destroy runs through the PID monitor and independent reads
      confirm workload, queue, compute environment, IAM, security group, and log
      group resources are absent.
- [x] Any AWS-managed inactive job definition is recorded as retained without
      representing it as a running or billable compute resource.
- [x] Terraform validation, documentation conventions, and all seven PR checks pass.
- [x] No hosted control-plane, production, customer-secret, or unrelated AWS
      resource is changed.

## Acceptance status

The exact-prefix preflight found no existing test resources. The reviewed create
plan had exactly nine creates, zero updates, and zero deletes. Monitored apply
succeeded with nine additions. The probe verified two attempts (exit `1`, then
`0`) and final `SUCCEEDED`. The exact destroy succeeded through the monitor;
independent reads found the compute environment, queue, roles, security group,
and log group absent, with zero resources in local state. One job definition
remains `INACTIVE` under AWS's documented 180-day retention behavior.

## Tests / validation performed

- `terraform fmt -check`, Terraform init, and validate passed. The reviewed
  create plan contained nine creates; the reviewed destroy plan contained nine
  deletes, with no updates or opposite actions.
- `python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Monitored apply `nova-batch-retry-458-create-nov23a1` started at
  `2026-11-23T18:31:05Z` (supervisor PID `79812`, root
  `/Users/adewale/Projects/davdeploy/docs/test/fixtures/nova-batch-retry-458`,
  log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-batch-retry-458-create-nov23a1.log`).
  It completed with nine added, zero changed, and zero destroyed. The probe
  verified two attempts: attempt one exit `1`, attempt two exit `0`, final job
  `SUCCEEDED`, with both attempt markers in their CloudWatch streams.
- The first two monitored destroy attempts failed before AWS changes because of
  CLI argument ordering and then a missing isolated provider cache. Corrected
  monitored destroy `nova-batch-retry-458-destroy-nov23a1-retry2` started at
  `2026-11-23T18:56:55Z` (supervisor PID `80414`, Terraform PID `80415`) and
  succeeded at `19:01:34Z`. Exact-prefix AWS reads confirmed workload resources
  absent, except the expected inactive AWS-managed job-definition record.
  Terraform state lists zero resources and the monitor has no active run.

## Evidence files produced

- `docs/test/fixtures/nova-batch-retry-458/main.tf`
- `docs/test/fixtures/nova-batch-retry-458/variables.tf`
- `docs/test/fixtures/nova-batch-retry-458/versions.tf`
- `docs/test/fixtures/nova-batch-retry-458/.terraform.lock.hcl`
- `docs/test/fixtures/nova-batch-retry-458/probe.py`
- `docs/test/test458.md`
- `docs/tickets/ticket458.md`

## Boundaries

Use only the exact `davdeploy-nova-batch-retry-<run-id>` names in account
`654654474502`, region `us-east-1`. Keep state and plans outside the repository.
Run Terraform apply/destroy only through the PID monitor and review saved plans
before mutation. Do not touch the hosted control plane, production resources,
customer credentials, Nova gates, or retained SageMaker lineage. Preserve
protected untracked `--only-show-errors` and `.venv-pr399/`.

## Follow-up work

This proves one simple retry-on-nonzero-exit path for an Amazon Linux Fargate
container. It does not prove retry filters, Spot or infrastructure retries,
application idempotency, private networking, Nova dispatch, or hosted lifecycle.
