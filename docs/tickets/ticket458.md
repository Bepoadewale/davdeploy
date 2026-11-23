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

- [ ] The saved create plan contains only the exact intended resources.
- [ ] AWS Batch records two attempts: attempt one exits `1`; attempt two exits
      `0`; the final job status is `SUCCEEDED`.
- [ ] Attempt markers are verified from the two CloudWatch log streams, while
      probe output omits IDs, stream names, job output, and AWS errors.
- [ ] Reviewed exact destroy runs through the PID monitor and independent reads
      confirm workload, queue, compute environment, IAM, security group, and log
      group resources are absent.
- [ ] Any AWS-managed inactive job definition is recorded as retained without
      representing it as a running or billable compute resource.
- [ ] Terraform validation, docs checks, and all seven PR checks pass.
- [ ] No hosted control-plane resource, production resource, customer secret,
      or unrelated AWS resource is changed.

## Acceptance status

The fixture and evidence records are prepared. No AWS write has occurred yet.

## Tests / validation performed

- `terraform fmt -check` — pending.
- Terraform init/validate and exact create/destroy plans — pending.
- `python3 scripts/check_doc_conventions.py` — pending.
- `git diff --check` — pending.
- Monitored AWS apply/probe/destroy and independent absence reads — pending.

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
