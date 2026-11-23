# test454 — Step Functions failure and Catch recovery

Date: 2026-11-23

Execution type: Controlled disposable AWS workload validation.

Customer repository: None; direct same-account AWS service test.

Commit: `bc44e0c` (fixture and initial evidence record).

PR: [#454](https://github.com/Bepoadewale/davdeploy/pull/454), merged as
`67913448c57e39eb3438242ef4ccc3bd567995ec`. Final head
`a1a07882e767ae5f05e9a338f63ca7eed3d92138` passed all seven checks in run
[45229243421](https://github.com/Bepoadewale/davdeploy/actions/runs/45229243421).
Initial head `eddbcd6ac3d47846c7e44a0a5ea3bcd9f71f3686` passed all seven
checks in run [45222597413](https://github.com/Bepoadewale/davdeploy/actions/runs/45222597413).
Probe fix head `04edcc4cc81e56c2e37c6b9bca83dc6fb9cbcf7a` passed all seven
checks in run `45225522977`. Evidence head
`c301c6f8330851c95d5d915b4f418c4d9bcee463` passed all seven checks in run
[45226919117](https://github.com/Bepoadewale/davdeploy/actions/runs/45226919117).

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The stack created five resources: one Lambda execution role, one Lambda
function, one Step Functions execution role with a single exact-function invoke
grant, one Standard state machine, and one inline role policy. The exact prefix
is `davdeploy-nova-stepfn-recovery-454-nov23a2`. The exact five-resource stack
was destroyed and independently confirmed absent. Terraform state is empty.
State, plan files, and the packaged Lambda artifact stayed outside the
repository.

## Commands executed

- PR #454 and its ticket/test evidence were opened before AWS writes; the PR was merged after all acceptance checks passed.
- Caller identity was verified as account `654654474502` in `us-east-1`; exact
  Step Functions, Lambda, and role names were absent. The monitor had 31
  records and no active operations.
- Terraform init and validation passed with the pinned AWS `5.100.0` and
  Archive `2.7.1` providers. The saved create plan contains exactly five
  creates, zero updates, and zero deletes. AWS's state-machine-definition
  validator returned `OK` with zero diagnostics.
- Initial monitored create `nova-stepfn-recovery-454-create-nov23a2` failed
  before making AWS calls because the Terraform subprocess did not inherit the
  AWS profile. It started at `2026-11-23T17:00:51Z` (supervisor PID 55932,
  Terraform PID 55933) and failed at `17:00:57Z`; exact-name reads confirmed
  no resources were created. A fresh five-create plan was saved. Monitored
  retry `nova-stepfn-recovery-454-create-retry-nov23a2` started at
  `2026-11-23T17:07:41Z` (supervisor PID 57855, Terraform PID 57856, root
  `/private/tmp/davdeploy-nova-stepfn-recovery-454-nov23a2`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-stepfn-recovery-454-create-retry-nov23a2.log`).
  It completed at `17:08:04Z` with five added, zero changed, and zero destroyed.
- The state-machine validator returned `OK` with zero diagnostics. The
  redacting probe executed a failure-and-Catch-recovery path and a normal
  success path. It observed `LambdaFunctionFailed` before recovery and
  `LambdaFunctionSucceeded` afterward; both outputs matched their unique
  markers. Two probe invocations ran four total executions, all terminal
  `SUCCEEDED`. Probe output contained booleans only; input and output were not
  printed.
- The reviewed destroy plan contained exactly five deletes, zero additions,
  and zero updates. Monitored run
  `nova-stepfn-recovery-454-destroy-nov23a2` started at
  `2026-11-23T17:15:59Z` (supervisor PID 60259, Terraform PID 60260, root
  `/private/tmp/davdeploy-nova-stepfn-recovery-454-nov23a2`, log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-stepfn-recovery-454-destroy-nov23a2.log`).
  It completed at `17:17:00Z` with zero additions, zero changes, and five
  destroys. Exact AWS reads found no test state machine, Lambda function, or
  IAM roles. Local state is empty; the monitor has 34 terminal records and no
  active operations.

## Acceptance criteria

- [x] The controlled Lambda error is recorded as a failed task event.
- [x] The Catch transition reaches the recovery task and the execution succeeds
      with the expected marker.
- [x] The separate non-failing execution succeeds without taking the recovery
      branch.
- [x] The probe prints no execution input/output or exception message.
- [x] The exact stack is destroyed through the Terraform monitor and AWS
      absence is independently verified.
- [x] Local checks and all seven required PR checks pass.
- [x] Evidence is described as direct same-account service behavior, not Nova
      dispatch or hosted execution.

## Observed result

The failure-path execution recorded `LambdaFunctionFailed`, entered the Catch
recovery state, and completed through the Lambda recovery task. Its output
contained the matching marker and recovery flag. The separate normal execution
completed without recovery and returned its matching marker. The first probe
check expected generic task-event names and exited nonzero even though both AWS
executions succeeded; after matching Lambda-specific event names, the probe
passed with four total successful executions and no execution data printed.

## Teardown

The reviewed exact five-resource destroy succeeded through the PID monitor.
AWS independently returned no test state machine, Lambda function, or IAM
roles; local state is empty and the monitor has no active operation. The hosted
control plane, production resources, and other customer resources were out of
scope.

## Final boundary

This is direct Step Functions and Lambda behavior evidence for one Standard
state-machine shape. It does not establish Nova dispatch, Step Functions role
policy safety for other integrations, hosted execution, or general customer
certification.
