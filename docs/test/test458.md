# test458 — AWS Batch first-attempt failure and retry recovery

Date: 2026-11-23

Execution type: Controlled disposable AWS workload validation.

Customer repository: None; direct same-account AWS Batch service test.

PR: [#458](https://github.com/Bepoadewale/davdeploy/pull/458), draft.

Commit: `4747a6f376deebd27519202ed05cd06be304fe71`.

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
- `terraform fmt -check`, init, and validate passed. The reviewed saved create
  plan contained exactly nine creates and no changes/deletes. Monitored apply
  `nova-batch-retry-458-create-nov23a1` started at `2026-11-23T18:31:05Z`
  (supervisor PID `79812`) and succeeded with nine additions. The redacted probe
  verified two attempts: the first failed, the retry succeeded, and the final
  job status was `SUCCEEDED`. Both attempt markers appeared in CloudWatch.
- The first two monitored destroy invocations stopped before AWS changes: one
  had an invalid Terraform argument order; the next lacked the isolated provider
  cache. The corrected monitored run `nova-batch-retry-458-destroy-nov23a1-retry2`
  started at `2026-11-23T18:56:55Z` (supervisor PID `80414`, Terraform PID
  `80415`) and succeeded at `19:01:34Z`. It applied the reviewed exact plan of
  nine deletions. The state now lists zero resources and the monitor has no
  active operation.
- Exact-prefix reads in verified account `654654474502`, `us-east-1`, found no
  compute environment, queue, IAM role, security group, or log group. One AWS
  Batch job definition remains `INACTIVE`; AWS retains deregistered definitions
  for up to 180 days before permanent deletion. It is not running compute.
- All seven PR checks passed on the tested head in CI run
  [45239562347](https://github.com/Bepoadewale/davdeploy/actions/runs/45239562347).

## Acceptance criteria

- [x] Attempt one exits `1`, AWS Batch retries, attempt two exits `0`, and the
      job succeeds.
- [x] Both attempt markers are present in the CloudWatch streams.
- [x] Probe output is redacted and contains only booleans and the attempt count.
- [x] The exact disposable stack is destroyed through the PID monitor and
      independently confirmed absent; the AWS-managed inactive job definition
      is recorded separately.

## Observed result

AWS Batch ran two attempts: attempt one exited `1`, attempt two exited `0`, and
the final job status was `SUCCEEDED`. Both expected attempt markers were
present. The probe emitted only booleans and an attempt count.

## Teardown

The exact Terraform stack was destroyed. Independent reads found its compute
environment, queue, roles, security group, and log group absent; local Terraform
state lists zero resources. AWS retains the deregistered job definition in
`INACTIVE` status for up to 180 days. No job or compute environment remains
running.

## Final boundary

This direct service test does not prove Nova dispatch, a hosted customer apply,
or general Batch support.
