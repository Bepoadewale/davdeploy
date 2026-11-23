# test458 — AWS Batch first-attempt failure and retry recovery

Date: 2026-11-23

Execution type: Controlled disposable AWS workload validation.

Customer repository: None; direct same-account AWS Batch service test.

PR: [#458](https://github.com/Bepoadewale/davdeploy/pull/458), draft.

Commit: Pending the first PR #458 fixture commit.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The fixture provisions one managed Fargate compute environment, job queue,
container job definition, two IAM roles and exact AWS-managed service-role
attachments, security group, and one-day CloudWatch log group. The job has two
attempts and exits nonzero on attempt one, then succeeds on attempt two using
the AWS-provided `AWS_BATCH_JOB_ATTEMPT` variable.

## Commands executed

- PR #458 and its ticket/test records were opened before AWS writes.
- Terraform format, init, validation, reviewed create/destroy plans, and the
  monitored AWS run — pending.

## Acceptance criteria

- [ ] Attempt one exits `1`, AWS Batch retries, attempt two exits `0`, and the
      job succeeds.
- [ ] Both attempt markers are present in the CloudWatch streams.
- [ ] Probe output is redacted and contains only boolean assertions/counts.
- [ ] The exact disposable stack is destroyed through the PID monitor and
      independently confirmed absent.

## Observed result

Pending the controlled AWS run.

## Teardown

Pending. Record AWS-managed inactive job-definition retention separately from
running compute or billable resources.

## Final boundary

This direct service test does not prove Nova dispatch, a hosted customer apply,
or general Batch support.
